# Cerberus - imagem do Sentinel de endpoint.
#
# ATENCAO: por padrao um container so enxerga os processos do PROPRIO
# container (namespace de PID isolado). Para monitorar a MAQUINA HOSPEDEIRA,
# execute com --pid=host --network=host e privilegios para encerrar processos
# (veja deploy/docker-compose.yml ou o README). Sem isso, o sentinel vigia
# apenas o que roda dentro do container.

FROM python:3.12-slim

LABEL org.opencontainers.image.title="Cerberus" \
      org.opencontainers.image.description="Sentinel de bloqueio de agentes nao autorizados"

WORKDIR /app
COPY pyproject.toml README.md ./
COPY cerberus ./cerberus
COPY config ./config

RUN pip install --no-cache-dir . && mkdir -p /var/log/cerberus

# Modo AUDITORIA por padrao. Para encerrar processos, acrescente --bloquear
# ao `docker run` (ou no command do compose) apos validar os eventos.
ENTRYPOINT ["cerberus"]
CMD ["sentinel", "--intervalo", "3", "--eventos", "/var/log/cerberus/eventos.jsonl"]
