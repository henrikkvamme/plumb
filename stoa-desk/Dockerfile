FROM node:24-slim AS build
WORKDIR /app
RUN npm install --global pnpm@11.21.0
COPY stoa-desk/package.json stoa-desk/pnpm-lock.yaml stoa-desk/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY stoa-desk/ ./
RUN pnpm build

FROM node:24-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.3 /uv /usr/local/bin/uv
ENV UV_PYTHON_INSTALL_DIR=/opt/python UV_LINK_MODE=copy
COPY stoa-desk/py/requirements.txt /tmp/requirements.txt
RUN uv venv --python 3.12 /opt/venv && VIRTUAL_ENV=/opt/venv uv pip install --no-cache -r /tmp/requirements.txt
WORKDIR /app/stoa-desk
ENV NODE_ENV=production PYTHONPATH=/app/stoa/src:/app/stoa-desk/py PYTHONUNBUFFERED=1
COPY --from=build --chown=node:node /app/package.json ./
COPY --from=build --chown=node:node /app/node_modules ./node_modules
COPY --from=build --chown=node:node /app/dist ./dist
COPY --chown=node:node stoa/src/bp /app/stoa/src/bp
COPY --chown=node:node stoa-desk/py/samples /app/stoa/data
COPY --chown=node:node stoa-desk/py/desk ./py/desk
COPY --chown=node:node stoa-desk/py/serve.sh ./py/serve.sh
RUN mkdir -p py/.cache py/.uploads /app/stoa/experiments \
  && chown -R node:node py /app/stoa/experiments \
  && /opt/venv/bin/python -c "import desk.remote, desk.store"
USER node
EXPOSE 3000
CMD ["sh", "py/serve.sh"]
