# Análise Java do QLabel 29.0.22

## Origem e limites

- Pacote: `com.rmicro.labelprinter`.
- APK: `captures/apk/QLabel_29.0.22.apk`, obtido do APKPure.
- SHA-256: `7428e16ac3c70e6ff412ff1fdb5e14dbfab4e76c019dc1a19f06c44b4f90fabe`.
- Ferramenta: JADX 1.5.6. Para ferramentas futuras, consultar os repositórios do CachyOS e o AUR e solicitar ao usuário a instalação nativa antes de baixar uma distribuição avulsa.
- Fontes locais: `captures/decompiled/qlabel/sources/`.
- Comando de decompilação: `jadx -j 2 --no-res -d captures/decompiled/qlabel captures/apk/QLabel_29.0.22.apk`.
- A execução original terminou com 111 erros reportados pelo JADX; o log está em `captures/decompiled-jadx.log`. Isso não significa que todos os métodos foram recuperados corretamente. Os métodos abaixo têm corpos Java disponíveis, mas ainda não foram comparados com captura Bluetooth ou execução na E210.

As conclusões descrevem o comportamento do aplicativo analisado. Ainda não há validação na impressora física. Os nomes de algumas operações vêm do aplicativo e não constituem especificação do fabricante.

## Caminho que atende à E210

Referências relativas à pasta de fontes:

| Etapa | Evidência |
| --- | --- |
| Nome do modelo | `com/yundayin/templet/Constant.java:16`: `E210 = "E210"` |
| Seleção do transporte | `com/rmicro/labelprinter/main/view/activity/ConnectionListActivity.java:367`: nomes começando com `E2` entram em `connectPrinterByAddressForYP1` |
| Conexão pelo endereço | `com/rmicro/labelprinter/bluetooth/LPBTService.java:1034`: delega a `BluetoothSdkManager.connect` |
| Socket | `com/rmicro/labelprinter/yp1sdk/service/BtService.java:231`: `createRfcommSocketToServiceRecord` |
| UUID | `com/rmicro/labelprinter/yp1sdk/constant/ConstantDefine.java:28`: `00001101-0000-1000-8000-00805F9B34FB` |
| Impressão | `com/rmicro/labelprinter/bluetooth/LPBTService.java:525`: conexão desse SDK segue para `printImage` |
| Codificação e comandos | `com/rmicro/labelprinter/yp1sdk/util/PrinterHelper.java` |

Portanto, o caminho encontrado para um dispositivo anunciado como E210 usa Bluetooth clássico via RFCOMM e UUID de porta serial. O canal RFCOMM numérico não aparece nessa constante: precisa ser descoberto no serviço da unidade real. Não presumir canal 1.

O aplicativo também contém BLE e outros SDKs, mas a existência deles não demonstra que sejam usados pela E210.

## Conexão e recepção

`LPBTService.initSDKManager` agenda `sendCheckMessage` 300 ms após o SDK informar estado conectado. Esse método envia `1B 5E`.

O receptor reconhece prefixos `1B 1E` e `1B 5E` e chama `parseData`. O terceiro byte é interpretado como estado: `01`, `FF`, `FE` e `FD` são mapeados para estados internos. Não há evidência suficiente para atribuir todos esses valores a condições físicas específicas.

Para estado `01`, `parseEN13` interpreta um campo de identificação de comprimento variável e dados de mídia: tipo, largura e altura em décimos, ângulo, material, cor e comprimento. Isso sugere comunicação sobre o consumível, mas não comprova exigência de autenticação ou bloqueio de etiquetas.

`showOptins` envia `1B 1E 01` como resposta em determinadas transições. Bytes isolados `E1` a `E8` são tratados como falha de impressão pelo callback.

A leitura do socket entrega os bytes disponíveis no momento, sem um enquadramento robusto de mensagens. Uma implementação Linux deve lidar com mensagens fragmentadas ou agrupadas, em vez de assumir que cada leitura corresponde a uma resposta completa.

## Sequência de impressão encontrada

Em `LPBTService.printImage`, linha 1539 em diante:

1. Configura densidade, deslocamentos horizontal e vertical e tipo de papel.
2. Redimensiona a imagem e converte para preto e branco.
3. Envia `1B 33`, chamado `setPrinterForAndroid` pelo SDK.
4. Configura dimensões e altura do raster com `setPrinterLabelParam`.
5. Envia as linhas codificadas por `getTargetPrintData`.
6. Envia `1B 4A 00` e depois `1B 69`, chamados de ajuste e avanço para próxima página pelo código.

| Operação no Java | Bytes em hexadecimal |
| --- | --- |
| Consulta de configurações/consumível | `1B 5E` |
| Resposta a notificação | `1B 1E 01` |
| Consulta de status disponível no helper | `1B 06` |
| Consulta de modelo disponível no helper | `1B 18` |
| Densidade | `1C 21 n` |
| Tipo de papel | `1C 25 n` |
| Deslocamento vertical | `1B 34 sinal magnitude` |
| Deslocamento horizontal | `1B 35 sinal magnitude` |
| Modo chamado “Android” | `1B 33` |
| Parâmetros da etiqueta | `1B 29 rasterHeightLE16 dimension1LE16 dimension2LE16 flags` |
| Linha da imagem | `1B 19 01 (N+1) offset payload` |
| Ajuste de avanço | `1B 4A 00` |
| Próxima página | `1B 69` |

No código, deslocamentos negativos viram sinal `1` e positivos ou zero viram `0`; a magnitude é enviada em um byte. A unidade física do deslocamento ainda precisa ser medida. O método de densidade limita o valor entre 0 e 16.

O aplicativo descreve os tipos de papel como: `0` contínuo, `1` furo de posicionamento, `2` intervalo entre etiquetas, `3` marca preta e `4` etiqueta de cabo. Isso deve ser validado para o modelo específico.

O helper inclui métodos CPCL e outros comandos que não são usados nesta sequência raster. Não classificar o protocolo completo da E210 como CPCL, TSPL ou ESC/POS apenas pela presença desses métodos ou pelo prefixo ESC.

## Dimensões e pixels

`printImage` recebe dois valores de dimensão cuja ordem depende da orientação em `drawBitmap`; os nomes das variáveis decompiladas são confusos. Para evitar trocar largura e altura, validar primeiro uma etiqueta retangular e sua orientação.

O aplicativo usa os seguintes cálculos:

- `d1 = int(primeira dimensão)`; `r = min(d1, 48)`.
- Largura do bitmap enviado: `r * 8` pixels.
- Altura do bitmap: `int(r * segunda dimensão / primeira dimensão) * 8` pixels.
- Parâmetros da etiqueta: `d1 * 10`, `int(segunda dimensão) * 10`, `altura do bitmap + 1`, `0`.
- No pacote `1B 29`, a altura do raster vem antes das duas dimensões, todas em little-endian de 16 bits.

Isso mostra uma escala de 8 pixels/mm e limite de 384 pixels na largura do raster nesse caminho do aplicativo. Ainda não é uma medição da resolução ou da largura física da unidade.

`getBitmapData_Y` chama `removeAlpha`, `sDither` e `get8BitDataH`. O empacotamento final é horizontal, linha por linha, com oito pixels por byte, pixel da esquerda no bit mais significativo, branco `0` e preto `1`. Pixels faltantes no último byte são preenchidos com zero.

## Formato de cada linha

Em `PrinterHelper.getTargetPrintData` (linha 1023) e `getImageCmd1B19` (linha 1520):

- Remove bytes `00` do começo e do fim da linha.
- `offset` é o número de bytes removidos do começo, não o número de pixels.
- `N` é a quantidade de bytes restantes no payload.
- O cabeçalho é `1B 19 01 (N+1) offset`.
- A linha totalmente branca também tem cabeçalho: `N = 0` e `offset = largura em bytes`.
- As linhas são concatenadas sem separador adicional nesse método.

Exemplos derivados do algoritmo, ainda não enviados à impressora:

| Raster de uma linha | Pacote |
| --- | --- |
| `00 80 01 00` | `1B 19 01 03 01 80 01` |
| `00 00 00 00` | `1B 19 01 01 04` |
| `FF FF FF FF` | `1B 19 01 05 00 FF FF FF FF` |

## Envio e dependências nativas

`PrinterHelper.WriteData` delega a `BluetoothSdkManager.print`, que mantém uma fila e envia por `BtService`. `ConnectedThread.write` escreve o array no `OutputStream` e chama `flush`. Não há fragmentação BLE, confirmação por linha ou temporização explícita por linha nesse caminho de envio. Isso não garante que a impressora tolere qualquer ritmo de envio ou elimine a necessidade de ler respostas.

Os métodos de montagem raster e de configuração rastreados possuem implementação Java. Não foi encontrada chamada a `libPrinterNative.so` nesses métodos; a análise nativa não é necessária para a primeira tentativa baseada nesse caminho. Pode haver comandos adicionais quando a etiqueta contém elementos especiais, como códigos de barras: `scaleImage` também chama `drawOneCode`. Começar a prova de conceito com uma imagem raster simples.

## Próxima validação

1. Descobrir a unidade no Linux, registrar nome anunciado e serviço/canal RFCOMM.
2. Conectar e observar a resposta à consulta `1B 5E`.
3. Comparar, se possível, com uma captura do Qlabel imprimindo uma etiqueta retangular conhecida.
4. Implementar o encoder e uma impressão raster simples, com dimensões explícitas e leitura de respostas.
5. Confirmar orientação, limites, avanço e erros no equipamento físico.
