# Investigação da E210

## Informações conhecidas

| Item | Informação | Fonte |
| --- | --- | --- |
| Modelo informado | E210 | Relato inicial do usuário |
| Tipo | Impressora térmica Bluetooth | Relato inicial do usuário |
| Aplicativo utilizado | Qlabel, disponível na Google Play Store | Relato inicial do usuário |
| Objetivo | Impressão direta pelo Linux | Escopo do projeto |

## Informações a coletar

- Identificação exata da impressora e dimensões das etiquetas usadas.
- URL do Qlabel na Play Store e versão instalada.
- Distribuição Linux, versão do kernel e adaptador Bluetooth.
- Nome anunciado pela impressora e informações de descoberta.
- Serviços Bluetooth e, caso use BLE, características GATT e suas propriedades.
- Captura de uma impressão bem-sucedida no aplicativo.

## Experimento inicial

Usar uma etiqueta de conteúdo simples e conhecido, por exemplo uma imagem pequena com uma borda e o texto `E210 Linux`. Registrar as dimensões do arquivo e da etiqueta e as opções selecionadas no aplicativo.

Comparar depois duas impressões que alterem apenas uma variável por vez, como conteúdo, largura ou quantidade de cópias. Preservar a ordem dos pacotes e os tempos de envio para investigar fragmentação e controle de fluxo.

O método de captura será definido conforme o telefone e o transporte disponíveis. Ainda não há captura ou evidência suficiente para especificar comandos de impressão.

## Registro de cada teste

```text
Data:
Equipamento / firmware:
Sistema / adaptador Bluetooth:
Aplicativo / versão, quando aplicável:
Objetivo:
Procedimento e comandos:
Entrada e configurações:
Resultado esperado:
Resultado observado:
Artefatos associados:
Conclusões confirmadas:
Hipóteses e próximo experimento:
```

## Critério de sucesso da prova de conceito

Uma etiqueta enviada pelo Linux deve ser impressa com o conteúdo e as dimensões esperados. O procedimento deve ser repetível após desconectar e reconectar a impressora, sem depender do aplicativo durante a impressão.
