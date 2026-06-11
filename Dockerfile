# PRIVATE production overlay: the public unshackle-tg framework image plus our private
# services and production config. No framework code lives here (single source of truth is the
# public repo). The IL-edge autossh tunnel + its deps are added on top for production.
FROM ghcr.io/avi-dev-user/unshackle-tg:latest

# IL-edge tunnel deps (orya autossh), not part of the generic public base.
RUN apt-get update && apt-get install -y --no-install-recommends openssh-client autossh \
    && rm -rf /var/lib/apt/lists/*

# Private services. JSON/TEST already ship in the public base /app/services, so drop the copies
# here to avoid duplicate service tags.
COPY services/ /app/services-extra/
RUN rm -rf /app/services-extra/JSON /app/services-extra/TEST
COPY services-commercial/ /app/services-commercial/

# Production config that lists all three service dirs + the region proxy.
COPY deploy/unshackle.yaml /app/unshackle.yaml
RUN cp /app/unshackle.yaml "$(python -c 'import sysconfig, os; print(os.path.join(sysconfig.get_paths()["purelib"], "unshackle"))')/unshackle.yaml" \
    && mkdir -p /root/.config/unshackle && cp /app/unshackle.yaml /root/.config/unshackle/unshackle.yaml

# Production process manager (engine + bot + IL-edge tunnel). Drop the base image's conf so
# its [program:engine]/[program:bot] aren't loaded a second time (supervisord reads all *.conf).
RUN rm -f /etc/supervisor/conf.d/*.conf
COPY deploy/supervisord.conf /etc/supervisor/conf.d/unshackle-bot.conf
