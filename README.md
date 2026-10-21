# E210 Thermal Printer Linux

Aplicação Python para imprimir imagens PNG na impressora térmica Bluetooth **E210 pelo Linux**, sem depender do celular ou do aplicativo Qlabel durante a impressão.

A impressão foi validada fisicamente em uma E210 com **papel contínuo de 50 mm**, usando CachyOS e BlueZ. Tanto o padrão geométrico quanto um PNG enviado pela linha de comando foram impressos corretamente.

## Requisitos

- Linux com BlueZ ativo e adaptador Bluetooth com suporte a Bluetooth clássico/RFCOMM.
- Python 3, Pillow, dbus-python e PyGObject.
- E210 ligada, com papel contínuo de 50 mm, sem conexão ativa com o celular.

A comunicação usa as APIs D-Bus atuais do BlueZ. Não é necessário instalar `sdptool` ou as ferramentas Bluetooth descontinuadas.

## Instalação

Clone o projeto e entre na pasta:

```bash
git clone https://github.com/ggvaldez/E210ThermalPrinterLinux.git
cd E210ThermalPrinterLinux
```

No CachyOS ou Arch Linux, instale as dependências nativas:

```bash
sudo pacman -S --needed bluez bluez-utils python python-pillow python-dbus python-gobject
sudo systemctl enable --now bluetooth.service
```

Em outras distribuições, instale os pacotes equivalentes pelo gerenciador da distribuição. A implementação não depende especificamente do CachyOS, mas outras distribuições ainda não foram testadas neste projeto. Os exemplos abaixo usam `python`; se sua distribuição disponibiliza o interpretador como `python3`, substitua o comando.

## Descobrir a impressora

Ligue a E210 e desconecte o Qlabel ou desative o Bluetooth do celular. No terminal, execute:

```bash
bluetoothctl
```

Dentro do `bluetoothctl`:

```text
power on
scan on
```

Aguarde aparecer uma linha semelhante a esta e anote o endereço da sua impressora:

```text
Device AA:BB:CC:DD:EE:FF E210
```

Encerre a busca e saia:

```text
scan off
quit
```

Na unidade testada, a conexão funcionou sem pareamento manual. O programa descobre o canal serial pelo UUID do serviço; não é necessário configurar um canal RFCOMM.

## Imprimir um PNG

Execute na raiz do projeto, substituindo o caminho da imagem e o endereço Bluetooth:

```bash
python tools/print_png.py imagem.png --address AA:BB:CC:DD:EE:FF
```

Cada execução imprime **uma cópia**. Caminhos com espaços devem ficar entre aspas.

A imagem é redimensionada para **384 pixels de largura**, preservando a proporção. Essa é a maior largura raster validada até agora, equivalente a **48 mm a 8 pixels/mm**, aproximadamente 203 dpi. Ainda não determinamos o limite físico absoluto da impressora.

Para máxima nitidez e controle pixel a pixel, prepare o PNG já com 384 pixels de largura. Um arquivo de 384 × 384 pixels produz um raster de aproximadamente 48 × 48 mm. Metadados DPI do PNG não alteram o tamanho; a altura é calculada a partir da proporção da imagem. O avanço e as margens físicas podem diferir do tamanho do raster.

Transparência é composta sobre fundo branco. Tons de cinza são convertidos para preto e branco com dithering Floyd–Steinberg. O envio mantém pausas de **20 ms entre comandos e linhas**, necessárias para a impressão correta nos testes realizados.

### Prévia sem imprimir

```bash
python tools/print_png.py imagem.png --dry-run --preview previa.png
```

Esse comando prepara a imagem sem conectar à impressora. A prévia não sobrescreve arquivos existentes.

### Ajustes

Para usar um limiar fixo de preto e branco, em vez de dithering:

```bash
python tools/print_png.py imagem.png --address AA:BB:CC:DD:EE:FF --threshold 128
```

Para ajustar a densidade térmica ou selecionar outro adaptador:

```bash
python tools/print_png.py imagem.png --address AA:BB:CC:DD:EE:FF --density 6 --adapter hci0
```

`--density` aceita valores de 0 a 16 e tem padrão 6. `--threshold` aceita de 0 a 255. Consulte todas as opções com:

```bash
python tools/print_png.py --help
```

## Diagnóstico

- **Erro ao importar PIL, dbus ou gi:** confira as dependências e use o Python do sistema que recebeu os pacotes nativos.
- **Não conecta:** confira a alimentação, o endereço Bluetooth e o serviço `bluetooth.service`; desconecte a impressora de outros dispositivos. A conta deve ter acesso ao serviço BlueZ no barramento D-Bus do sistema.
- **Pontos na mesma linha ou desenho incompleto:** use o comando de PNG, que já inclui as pausas entre envios. O primeiro teste sem pausas falhou dessa forma.
- **Demora para imprimir:** a pausa de 20 ms limita o envio a aproximadamente 50 linhas por segundo, além do tempo de conexão e processamento.

Para consultar o status sem imprimir:

```bash
python tools/probe_bluez.py AA:BB:CC:DD:EE:FF --query status --timeout 20
```

“Envio concluído” confirma a transferência ao socket, não a saída física do papel. Nos testes, a impressão correta foi confirmada por observação do usuário.

## Outras impressoras e plataformas

**Precisa de suporte a outra impressora ou a outra plataforma, como Windows ou macOS? [Abra uma issue](https://github.com/ggvaldez/E210ThermalPrinterLinux/issues).**

Informe o modelo exato, o sistema operacional e sua versão e, se houver, o aplicativo que funciona com o equipamento. Essas informações ajudam a investigar a compatibilidade. Novos modelos e plataformas ainda precisam de implementação e testes.

A conversão de PNG e a codificação dos comandos usam Python e podem ser reaproveitadas em outras plataformas. A conexão atual depende do BlueZ no Linux. Não presumimos que outras impressoras usem o mesmo protocolo da E210.

## Desenvolvimento e documentação

Para executar os testes automatizados:

```bash
python -m unittest discover -s tests -v
```

- [Análise Java e formato dos comandos](docs/ANALISE_JAVA.md)
- [Conexão BlueZ e resultados dos testes físicos](docs/BLUETOOTH_LINUX.md)
- [Roteiro de investigação](docs/INVESTIGACAO.md)
- [Roadmap](ROADMAP.md)

O Qlabel 29.0.22 serviu de referência para investigar o protocolo. A aplicação Python não precisa do APK, do Android ou de bibliotecas nativas extraídas do aplicativo para funcionar.

APKs, decompilações, logs e capturas locais ficam fora do controle de versão. Revise identificadores de dispositivos antes de publicar capturas ou logs em uma issue.
