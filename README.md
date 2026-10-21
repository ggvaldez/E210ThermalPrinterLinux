# E210 Thermal Printer Linux

Projeto para permitir o uso da impressora térmica Bluetooth E210 no Linux, sem depender de um celular.

Segundo o relato inicial do projeto, a forma de impressão disponível atualmente é o aplicativo **Qlabel**, distribuído na Google Play Store. O objetivo é identificar o transporte e o protocolo usados pela impressora e implementar uma ferramenta de impressão para Linux.

## Estado atual

Fase de investigação. Ainda não existe driver ou ferramenta funcional neste repositório. Não foram confirmados o fabricante, as variantes do modelo, a resolução, a largura de impressão ou o protocolo.

Não presumimos que a E210 use ESC/POS, TSPL, CPCL ou outro protocolo conhecido. Também precisamos verificar se a comunicação ocorre por Bluetooth clássico, BLE ou ambos.

## Primeiro marco

Imprimir uma etiqueta de teste a partir do Linux, com instruções reproduzíveis e sem usar o celular durante a impressão.

## Plano

1. Identificar a unidade física, o aplicativo e o ambiente Linux.
2. Descobrir os serviços e as características Bluetooth expostos pela impressora.
3. Obter uma captura de uma impressão conhecida realizada pelo Qlabel.
4. Documentar os comandos, o formato da imagem e o fluxo de comunicação observados.
5. Implementar uma prova de conceito e validar a impressão na impressora real.
6. Evoluir para uma interface de linha de comando e avaliar integração com CUPS.

Consulte [ROADMAP.md](ROADMAP.md) e o [roteiro de investigação](docs/INVESTIGACAO.md).

## Desenvolvimento

A linguagem e as dependências serão definidas após identificar o transporte e o protocolo. Cada descoberta deve indicar sua fonte, as condições do teste e o resultado observado, distinguindo fatos de hipóteses.

Capturas podem conter endereços Bluetooth e outros identificadores. Revise esses dados antes de incluí-los no repositório público.
