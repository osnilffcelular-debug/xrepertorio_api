# XRepertório

Aplicativo Flutter para repertório musical e espelhamento de palco.

## Gerar o app iOS com Codemagic

O build para iPhone exige macOS e Xcode. O workflow em `codemagic.yaml` compila
um IPA assinado e guarda o arquivo nos artefatos do build; ele não publica nem
envia o app automaticamente ao App Store Connect.

Antes de iniciar o build:

1. Coloque o projeto em um repositório Git privado e conecte-o ao Codemagic.
   Não envie arquivos `.env`, chaves privadas ou certificados ao repositório.
2. Tenha uma conta Apple Developer ativa e registre o Bundle ID
   `com.osnilins.xrepertorio` no Apple Developer.
3. No Codemagic, configure a integração Apple Developer Portal / App Store
   Connect com uma chave de API. Dê à integração o nome exato
   `XRepertorio App Store Connect`, usado no YAML.
4. Em **Code signing identities**, busque ou envie um certificado Apple
   Distribution e um provisioning profile App Store para esse Bundle ID.
5. Se for distribuir pelo TestFlight, crie também o registro do app no App Store
   Connect. O workflow atual apenas gera o IPA; o envio ao TestFlight é manual.
6. Inicie o workflow `XRepertório iOS IPA` no Codemagic e baixe
   `build/ios/ipa/*.ipa` nos artefatos do build concluído.

O identificador do app não deve ser alterado depois que o app for criado no
App Store Connect. A assinatura e as credenciais ficam no Codemagic/Apple; não
armazene-as neste projeto.
