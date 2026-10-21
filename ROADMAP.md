# Roadmap

## 1. Identificação e comunicação

- [ ] Registrar fotos ou informações da etiqueta do equipamento, variante e firmware, se disponíveis.
- [x] Identificar o Qlabel por URL da Play Store, nome do pacote e versão.
- [ ] Registrar distribuição Linux, kernel e adaptador Bluetooth usados nos testes.
- [ ] Verificar descoberta e pareamento no Linux.
- [x] Identificar o transporte usado no caminho testado: Bluetooth clássico/RFCOMM.
- [ ] Registrar serviços, UUIDs, características e propriedades disponíveis.

## 2. Protocolo

- [ ] Capturar uma sessão de impressão conhecida com o Qlabel.
- [ ] Relacionar os dados enviados ao conteúdo e às dimensões da etiqueta.
- [x] Identificar configuração, codificação raster e finalização para a prova de conceito.
- [ ] Determinar fragmentação, limites de envio, confirmações e temporização.
- [x] Documentar o caminho raster com exemplos e nível de confiança das conclusões.

## 3. Prova de conceito Linux

- [x] Implementar conexão e envio com base no protocolo observado.
- [x] Imprimir uma etiqueta de teste na E210 física.
- [x] Registrar o procedimento completo e os resultados.
- [ ] Tratar desconexão, indisponibilidade e erros observados.

## 4. Uso cotidiano

- [x] Implementar conversão de PNG para o formato aceito pela impressora.
- [x] Disponibilizar interface de linha de comando.
- [x] Documentar instalação, permissões e solução de problemas.
- [x] Adicionar testes para os componentes de protocolo e imagem.
- [ ] Avaliar integração com CUPS após estabilizar a impressão direta.
