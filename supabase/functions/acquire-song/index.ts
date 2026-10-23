import { createClient } from "npm:@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, content-type, apikey",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

interface RequestBody {
  musica_id?: string;
  nome_musica?: string;
  artista?: string;
  priority?: number;
}

interface MusicRecord {
  id: string;
  nome_musica: string;
  artista_id: string;
  status: string;
  url_guitarra: string | null;
  url_baixo: string | null;
  url_piano: string | null;
  url_bateria: string | null;
  url_outros: string | null;
  url_voz: string | null;
  letra_cifra: string | null;
  tom: string | null;
  bpm_original: number | null;
  created_at: string;
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    const body: RequestBody = await req.json();
    const { musica_id, nome_musica, artista, priority = 1 } = body;

    const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
    const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
    const githubToken = Deno.env.get("GITHUB_TOKEN");
    const githubRepo = Deno.env.get("GITHUB_REPOSITORY");

    const adminSupabase = createClient(supabaseUrl, serviceRoleKey, {
      auth: { autoRefreshToken: false, persistSession: false },
    });

    let record: MusicRecord | null = null;
    let isNewRecord = false;

    if (musica_id) {
      const { data, error } = await adminSupabase
        .from("repertorio_global")
        .select("*")
        .eq("id", musica_id)
        .maybeSingle();
      if (error) throw error;
      record = data;
    } else if (nome_musica && artista) {
      const { data: artistaData, error: artistaError } = await adminSupabase
        .from("artistas")
        .select("id")
        .ilike("nome_artista", artista)
        .limit(1)
        .maybeSingle();

      let artistaId: string;
      if (artistaError || !artistaData) {
        const { data: newArtista, error: insertError } = await adminSupabase
          .from("artistas")
          .insert({ nome_artista: artista.toUpperCase() })
          .select("id")
          .single();
        if (insertError) throw insertError;
        artistaId = newArtista.id;
      } else {
        artistaId = artistaData.id;
      }

      const { data: existing, error: existingError } = await adminSupabase
        .from("repertorio_global")
        .select("*")
        .eq("nome_musica", nome_musica.toUpperCase())
        .eq("artista_id", artistaId)
        .maybeSingle();

      if (existingError) throw existingError;

      if (existing) {
        record = existing;
      } else {
        const { data: newRecord, error: insertError } = await adminSupabase
          .from("repertorio_global")
          .insert({
            nome_musica: nome_musica.toUpperCase(),
            artista_id: artistaId,
            status: "pending",
            priority: priority,
          })
          .select("*")
          .single();

        if (insertError) throw insertError;
        record = newRecord;
        isNewRecord = true;
      }
    } else {
      return new Response(
        JSON.stringify({
          sucesso: false,
          mensagem: "Forneça musica_id OU (nome_musica + artista)",
        }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    if (!record) {
      return new Response(
        JSON.stringify({ sucesso: false, mensagem: "Música não encontrada" }),
        { status: 404, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // Se já está completed e tem TODAS as 6 stems, retorna imediatamente
    const stemsProntas = record.url_guitarra && record.url_baixo && record.url_piano && record.url_outros && record.url_bateria && record.url_voz;
    if (record.status === "completed" && stemsProntas) {
      return new Response(
        JSON.stringify({
          sucesso: true,
          status: "completed",
          musica: record,
          mensagem: "Música já processada e pronta para tocar",
          acao: "play",
        }),
        { headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // Atualiza status para pending com prioridade
    const { error: updateError } = await adminSupabase
      .from("repertorio_global")
      .update({
        status: "pending",
        priority: priority,
        erro_processamento: null,
      })
      .eq("id", record.id);

    if (updateError) throw updateError;

    // Se foi uma busca por nome+artista e não existia, loga em search_misses
    if (isNewRecord && nome_musica && artista) {
      try {
        const query = `${artista} - ${nome_musica}`.trim();
        await adminSupabase.from("search_misses").insert({
          query,
        });
        console.log(`[acquire-song] Logado search_miss: ${query}`);
      } catch (e) {
        console.warn("[acquire-song] Falha ao logar search_miss:", e);
      }
    }

    // Dispara GitHub Actions workflow se token estiver configurado
    let workflowDisparado = false;
    if (githubToken && githubRepo) {
      try {
        const dispatchUrl = `https://api.github.com/repos/${githubRepo}/actions/workflows/process-queue.yml/dispatches`;
        const response = await fetch(dispatchUrl, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${githubToken}`,
            Accept: "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
          },
          body: JSON.stringify({
            ref: "main",
            inputs: {
              max_items: "1",
              priority: priority.toString(),
              id: record.id,
            },
          }),
        });

        if (response.ok || response.status === 204) {
          workflowDisparado = true;
          console.log(`[acquire-song] GitHub Actions disparado para música ${record.id}`);
        } else {
          const errorText = await response.text();
          console.warn(`[acquire-song] Falha ao disparar GitHub Actions: ${response.status} - ${errorText}`);
        }
      } catch (e) {
        console.warn(`[acquire-song] Erro ao disparar GitHub Actions: ${e}`);
      }
    }

    // Retorna status para o app fazer polling
    return new Response(
      JSON.stringify({
        sucesso: true,
        status: "pending",
        musica: { ...record, status: "pending" },
        mensagem: workflowDisparado
          ? "Processamento iniciado! Aguarde alguns minutos."
          : "Música na fila. Processamento iniciará no próximo ciclo automático.",
        acao: "poll",
        poll_interval_seconds: 10,
        estimated_time_seconds: workflowDisparado ? 180 : 14400,
        workflow_disparado: workflowDisparado,
      }),
      { headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  } catch (error) {
    console.error("[acquire-song] Erro:", error);
    return new Response(
      JSON.stringify({
        sucesso: false,
        mensagem: error instanceof Error ? error.message : "Erro interno",
      }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});