# Roadmap

## 1. Identificação e comunicação

- [ ] Registrar fotos ou informações da etiqueta do equipamento, variante e firmware, se disponíveis.
- [ ] Identificar o Qlabel por URL da Play Store, nome do pacote e versão.
- [ ] Registrar distribuição Linux, kernel e adaptador Bluetooth usados nos testes.
- [ ] Verificar descoberta e pareamento no Linux.
- [ ] Identificar o transporte: Bluetooth clássico, BLE ou ambos.
- [ ] Registrar serviços, UUIDs, características e propriedades disponíveis.

## 2. Protocolo

- [ ] Capturar uma sessão de impressão conhecida com o Qlabel.
- [ ] Relacionar os dados enviados ao conteúdo e às dimensões da etiqueta.
- [ ] Identificar inicialização, configuração, codificação da imagem e finalização.
- [ ] Determinar fragmentação, limites de envio, confirmações e temporização.
- [ ] Documentar o protocolo com exemplos e nível de confiança das conclusões.

## 3. Prova de conceito Linux

- [ ] Implementar conexão e envio com base no protocolo observado.
- [ ] Imprimir uma etiqueta de teste na E210 física.
- [ ] Registrar o procedimento completo e os resultados.
- [ ] Tratar desconexão, indisponibilidade e erros observados.

## 4. Uso cotidiano

- [ ] Implementar conversão de imagem para o formato aceito pela impressora.
- [ ] Disponibilizar interface de linha de comando.
- [ ] Documentar instalação, permissões e solução de problemas.
- [ ] Adicionar testes para os componentes de protocolo e imagem.
- [ ] Avaliar integração com CUPS após estabilizar a impressão direta.
