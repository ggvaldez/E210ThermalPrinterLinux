# Diagnóstico Bluetooth com BlueZ

## Comportamento atual validado

A sequência atual de cada cópia é `configuração → raster → 1B 69 → 1B 4A 00`, sem pausas artificiais por padrão e sem espera adicional de finalização. Essa ordem é usada para todos os tipos de mídia; o comando `1C 25 n` continua distinguindo contínuo, intervalo e marca preta. O avanço em etiquetas com sensor precisa ser reconfirmado após essa alteração. As seções abaixo preservam o histórico da investigação, incluindo a ordem inicial extraída do Java que foi substituída após os testes físicos.

Teste decisivo em papel contínuo: vinte escadas consecutivas de vinte degraus (400 degraus de 1 mm no total), 87.160 bytes, enviadas sem pausas com os comandos finais invertidos em relação ao APK. O usuário confirmou todas completas e coladas. Houve pausas durante a execução, sem perda de conteúdo observada. Isso valida esse fluxo, mas não mede o buffer interno, pois o transporte pode controlar a entrega enquanto a impressora processa.

Antes disso, a escada sem comandos finais expôs somente até o início do 15º degrau. Enviar `1B 4A 00` isolado avançou o papel, e enviar `1B 69` depois fez imprimir o restante. Duas escadas terminadas somente com `1B 69` saíram coladas, mas com quinze degraus cada; com `1B 69` seguido de `1B 4A 00`, ambas tiveram vinte degraus. A semântica completa de cada comando ainda não foi determinada. Uma escada isolada terminou com avanço; a hipótese de posicionamento para destaque ao ficar ociosa é compatível com a observação, mas não foi confirmada como regra do firmware.

Logs locais: `captures/print-staircase-no-final.jsonl`, `captures/staircase-final-command-1b4a00.jsonl`, `captures/staircase-final-command-1b69.jsonl`, `captures/print-two-staircases-no-feed.jsonl`, `captures/print-two-staircases-reversed-final.jsonl`, `captures/print-staircase-separated-first.jsonl` e `captures/print-20-staircases-continuous.jsonl`.

Usamos as APIs D-Bus `Adapter1`, `ProfileManager1`, `Profile1` e `Device1.ConnectProfile`, sem `sdptool` ou `rfcomm` da coleção de ferramentas descontinuadas.

O cliente registra um perfil serial de saída com UUID `00001101-0000-1000-8000-00805f9b34fb`. O BlueZ descobre o serviço remoto e entrega um descritor de socket pelo callback `Profile1.NewConnection`. Assim não é preciso escolher um canal RFCOMM manualmente.

Documentação oficial:

- https://bluez.readthedocs.io/en/latest/profile-api/
- https://bluez.readthedocs.io/en/latest/device-api/

## Dependências nativas

No CachyOS/Arch: BlueZ ativo, Python, `python-dbus` e `python-gobject`. Os bindings Python já estavam disponíveis no ambiente do primeiro teste. Caso faltem, solicitar ao usuário a instalação pelos repositórios.

## Uso

Ligar a E210 e encerrar conexões de outros dispositivos. Obter o endereço Bluetooth por descoberta, por exemplo com `bluetoothctl`. Não é necessário colocar o computador em modo visível.

Somente conectar:

```bash
python tools/probe_bluez.py ENDERECO_BLUETOOTH
```

Conectar e enviar a consulta de configurações encontrada no aplicativo:

```bash
python tools/probe_bluez.py ENDERECO_BLUETOOTH --query --timeout 25
```

Outras consultas identificadas no helper Java:

```bash
python tools/probe_bluez.py ENDERECO_BLUETOOTH --query status --timeout 20
python tools/probe_bluez.py ENDERECO_BLUETOOTH --query model --timeout 20
```

`--query` sem valor continua selecionando `settings`. As únicas opções de consulta são `settings`, `status` e `model`; não há entrada livre de comandos. A ferramenta registra bytes brutos: receber bytes não significa que a resposta esteja completa ou semanticamente válida.

O prazo inclui descoberta, conexão e recepção. A saída é JSON por evento. Os modos de consulta não enviam impressão; a impressão exige `--print-test`. O cliente não altera a propriedade `Trusted`. Ao terminar, fecha o socket, encerra sua sessão de descoberta e remove o perfil temporário. O retorno é diferente de zero se a conexão falhar ou se uma consulta terminar sem resposta.

## Primeiro teste físico — 2026-10-20

- Impressora descoberta pelo nome `E210`.
- Serviço Serial Port anunciado, com o UUID esperado pelo Java.
- BlueZ 5.87; bindings `dbus` e `gi` já instalados.
- Registro do perfil cliente e conexão D-Bus bem-sucedidos.
- O socket recebido informou canal remoto RFCOMM **1** nesta unidade.
- Consulta `1B 5E` enviada após 300 ms da conexão.
- Nenhum byte recebido até o fim do prazo total de 25 segundos.
- Nenhum comando de impressão enviado.

O endereço da unidade fica fora desta documentação pública. O canal observado não deve ser fixado como constante para todas as unidades: o BlueZ deve continuar descobrindo o serviço.

O resultado confirma a conexão serial, mas não confirma uma troca completa do protocolo. Próximos experimentos: verificar consultas de status/modelo presentes no helper e comparar com uma sessão real do Qlabel, mantendo os bytes brutos e tempos de cada teste.

## Consultas de status e modelo — 2026-10-20

Cada consulta foi realizada em uma conexão própria, via Profile1, no canal resolvido pelo BlueZ. Prazo total de 20 segundos por execução. Nenhum comando de impressão foi enviado.

| Consulta | Enviado | Recebido, concatenado até o fim do teste | Resultado |
| --- | --- | --- | --- |
| Status | `1B 06` | `1B 06 00 03` | Comunicação bidirecional confirmada |
| Modelo | `1B 18` | `1B 18` | Apenas o prefixo; identificação do modelo não obtida |

O helper `getPrintStatus` lê o byte de índice 2, que nessa resposta é `00`. Não atribuímos significado ao byte adicional `03` nem declaramos a impressora pronta: faltam testes controlados para associar os campos às condições físicas.

O método Java `getRDPrinterModel` espera um byte de comprimento após `1B 18`, seguido do nome. Esse campo não chegou. Portanto, a resposta à consulta de modelo não atende ao formato esperado por esse método do aplicativo. Não assumir que os comandos genéricos do SDK são todos suportados pelo firmware da E210.

Logs locais ignorados pelo Git: `captures/probe-status.jsonl` e `captures/probe-model.jsonl`.

Próximo marco: preparar uma etiqueta raster simples conforme a sequência encontrada no Java, definir as dimensões a partir da mídia instalada e validar uma impressão física.

## Primeiro envio raster — papel contínuo de 50 mm

O usuário informou mídia contínua com largura de 50 mm. Foi preparada uma única impressão com comprimento lógico de 20 mm, densidade 6, deslocamentos zero e papel tipo 0. O raster segue o cálculo Java para 50 x 20 mm: 384 x 152 pixels, aproximadamente 48 x 19 mm na escala de 8 pixels/mm usada pelo aplicativo.

O padrão contém moldura, quadrado no canto e três barras de alturas diferentes. `tools/e210_raster.py` gera o raster e a sequência de comandos sem dependências adicionais. Os testes `tests/test_raster.py` verificam vetores de linha derivados do Java e decodificam o pacote completo para compará-lo ao raster original.

```bash
python -m unittest discover -s tests -v
python tools/probe_bluez.py ENDERECO_BLUETOOTH --print-test --timeout 25
```

O segundo comando imprime uma vez; não executar novamente sem necessidade. O retorno de sucesso indica envio completo ao socket, não confirmação física de impressão.

Artefatos locais: `captures/test-50mm-continuous.pbm`, `captures/test-50mm-continuous.bin` e `captures/print-test-50mm.jsonl`. O primeiro envio transferiu 7.046 bytes ao socket. O usuário observou apenas alguns pontos em uma mesma linha, sem avanço perceptível do papel. **O teste de impressão falhou**, apesar do envio completo ao socket e dos testes do encoder passarem.

Esse resultado ainda não distingue formato não aceito pelo firmware, comandos de configuração/avanço inadequados, ritmo de envio ou condição mecânica da mídia. Não foi identificada uma causa confirmada na revisão do Java. O programa de teste agrupa a sequência em um buffer, enquanto o aplicativo faz chamadas de escrita separadas para configuração, raster e avanço; isso é uma diferença a investigar, não uma causa demonstrada.

## Isolamento do avanço

Foi adicionado um modo que envia apenas `1B 4A 20`, equivalente a `PrinterHelper.setPrinterPageRun(32)`. O comando está no helper do APK, mas o método que aceita valor não foi encontrado em uso no caminho principal de impressão rastreado. Sua unidade física e seu comportamento na E210 ainda precisam de confirmação.

```bash
python tools/probe_bluez.py ENDERECO_BLUETOOTH --feed-test --timeout 15
```

Esse teste não envia raster, não altera a configuração e não tenta reiniciar a impressora. Log local: `captures/feed-test-32.jsonl`. O usuário confirmou um pequeno avanço do papel: o comando foi aceito e houve movimento físico. A distância não foi medida.

## Mesmo raster com pausas de envio

Após confirmar o avanço isolado, foi repetido o padrão original com pausas de 20 ms entre comandos e linhas. O objetivo é investigar limitação de ritmo de recepção/processamento, sem alterar o conteúdo do trabalho. São os mesmos 7.046 bytes em 160 blocos: seis comandos de configuração, 152 linhas e dois comandos finais.

O teste automatizado confirma que concatenar os blocos reproduz exatamente o pacote original. A separação de escritas não garante limites de pacotes no transporte RFCOMM: as pausas são o parâmetro experimental.

```bash
python tools/probe_bluez.py ENDERECO_BLUETOOTH --paced-print-test --timeout 25
```

O envio foi completado ao socket. O usuário confirmou a impressão de moldura, quadrado e três barras de tamanhos progressivamente maiores, como previsto pelo raster. Esse é o primeiro teste de impressão física bem-sucedido. O resultado sustenta a hipótese de limitação de ritmo, sem determinar ainda a menor pausa confiável. Log local: `captures/print-test-paced.jsonl`.

## Impressão de PNG

`tools/print_png.py` prepara arquivos PNG por meio de `tools/png_job.py` e reutiliza a conexão BlueZ do diagnóstico. O padrão é raster de 384 pixels, proporção preservada, mídia contínua de 50 mm e densidade 6. Transparência é composta sobre branco, seguida de redimensionamento e conversão monocromática. Há opções de prévia, limiar e preparação sem impressão. Consulte o README para os comandos.

O arquivo local `teste.png` foi enviado pela interface de PNG como raster de 384 × 384 pixels (48 × 48 mm), totalizando 11.713 bytes. O usuário confirmou que a impressão funcionou perfeitamente. O arquivo fornecido pelo usuário permanece local, fora deste commit. Log local: `captures/print-teste-png.jsonl`.

## Etiquetas com intervalo e cópias

Revisão Java: `EditSetActivity.ZZClick.onClick` associa a seleção de intervalo a `paperType = 2`, marca preta a `3` e contínuo a `0`. `PrintActivity` monta listas de páginas/cópias, e `LPBTService.startToPrint` percorre essas páginas. Cada `printImage` configura o papel e termina com `1B 4A 00` e `1B 69` antes de passar à página seguinte.

A interface Python aceita `--media`, `--label-height` e `--copies`. A quantidade é implementada repetindo o trabalho completo. As dimensões do papel são separadas das dimensões do raster: uma imagem de 48 × 48 mm pode usar uma etiqueta lógica de 50 × 50 mm.

Após o usuário trocar a mídia, foi solicitado um teste de três cópias. A mídia foi assumida como etiquetas de 50 × 50 mm com intervalo, pois as dimensões e o sensor ainda não foram medidos. Trabalho: `teste.png`, raster 384 × 384, `1C 25 02`, dimensões lógicas 500/500 em décimos de mm, três páginas, 35.139 bytes. Log local: `captures/print-gap-three-copies.jsonl`. A quantidade física e o alinhamento aguardam confirmação do usuário.

## Comparação de ritmo em bloco preto

Em papel contínuo, foi impresso um bloco inteiramente preto de 384 × 400 pixels (48 × 50 mm), com densidade 10. Com pausas de 20 ms, o usuário observou boa impressão na primeira metade e trancos do motor na segunda. Foi enviado depois o mesmo bloco com pausas de 50 ms, mas não houve avaliação física explícita desse resultado antes do experimento seguinte.

A pedido do usuário, o bloco foi enviado novamente com `--pause-ms 0`: os mesmos 21.230 bytes, em sequência e sem pausas artificiais. O usuário confirmou que **imprimiu melhor**. Isso demonstra melhora nesse teste sem pausas, mas não prova uma causa térmica, elétrica ou de buffering, nem estabelece que esse ritmo seja melhor para todas as imagens.

O resultado contrastou com o primeiro padrão geométrico, que falhou sem pausas e funcionou com 20 ms. A investigação posterior dos comandos finais substituiu essa configuração inicial pelo comportamento descrito no começo deste documento. Logs locais: `captures/print-black-48x50mm-density10.jsonl`, `captures/print-black-48x50mm-density10-pause50.jsonl` e `captures/print-black-48x50mm-density10-pause0.jsonl`.
