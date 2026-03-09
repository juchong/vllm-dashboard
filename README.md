# vLLM Dashboard

Web dashboard for managing [vLLM](https://github.com/vllm-project/vllm) inference servers. Switch models, monitor GPUs, download from HuggingFace—without touching the terminal.

## Features

- **Model switching** — one-click activation with container recreation and image pulling
- **Config management** — YAML configs with CLI import, per-model environment overrides
- **Model downloads** — background downloads with progress, resume, and auto-config generation
- **GPU monitoring** — real-time temperature, VRAM, power, utilization via WebSocket
- **User management** — role-based access (viewer, operator, admin) with password change
- **Dark mode** — system preference detection

## Screenshots

| Dashboard | Settings |
|-----------|----------|
| ![Dashboard](docs/pictures/dashboard.png) | ![Settings](docs/pictures/settings.png) |

| Core Settings | Advanced Settings | Environment |
|---------------|-------------------|-------------|
| ![Core](docs/pictures/model_core_settings.png) | ![Advanced](docs/pictures/model_advanced_settings.png) | ![Environment](docs/pictures/model_environment_settings.png) |

| Containers |
|------------|
| ![Containers](docs/pictures/containers.png) |

## Quick Start

**Prerequisites:** Docker with Compose, NVIDIA GPU + drivers, NVIDIA Container Toolkit.

```bash
# Create config directory
mkdir -p configs

# Create a model config
cat > configs/my-model.yaml << 'EOF'
model: mistralai/Devstral-Small-2-24B-Instruct-2512
served_model_name: Devstral-Small
tensor_parallel_size: 2
max_model_len: 131072
trust_remote_code: true
EOF

# Create hardware env file
cat > configs/env.hardware << 'EOF'
TORCH_CUDA_ARCH_LIST=8.9
HF_HUB_ENABLE_HF_TRANSFER=1
EOF

# Build and start
docker compose build && docker compose up -d

# Open http://localhost:8080
```

<details>
<summary>docker-compose.yml</summary>

```yaml
services:
  vllm:
    image: ${VLLM_IMAGE:-vllm/vllm-openai:latest}
    container_name: vllm
    ipc: host
    restart: unless-stopped
    volumes:
      - /path/to/models:/root/.cache/huggingface
      - ./configs:/root/.cache/vllm/configs
    env_file:
      - ./configs/env.active
    environment:
      - VLLM_API_KEY=${VLLM_API_KEY:-local}
      - HUGGING_FACE_HUB_TOKEN=${HUGGING_FACE_HUB_TOKEN:-}
    command: --config /root/.cache/vllm/configs/active.yaml
    deploy:
      resources:
        reservations:
          devices:
            - { driver: nvidia, count: all, capabilities: [gpu] }

  vllm-dashboard-backend:
    build: ./backend
    container_name: vllm-dashboard-backend
    restart: unless-stopped
    environment:
      - VLLM_MODELS_DIR=/models
      - VLLM_CONFIG_DIR=/vllm-configs
      - VLLM_COMPOSE_PATH=/vllm-compose
      - HUGGING_FACE_HUB_TOKEN=${HUGGING_FACE_HUB_TOKEN:-}
      - INITIAL_ADMIN_PASSWORD=${INITIAL_ADMIN_PASSWORD:-}
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ./:/vllm-compose:ro
      - /path/to/models:/models
      - ./configs:/vllm-configs
    deploy:
      resources:
        reservations:
          devices:
            - { driver: nvidia, count: all, capabilities: [gpu] }

  vllm-dashboard-frontend:
    build: ./frontend
    container_name: vllm-dashboard-frontend
    restart: unless-stopped
    depends_on: [vllm-dashboard-backend]
    ports: ["8080:80"]
```
</details>

## Configuration

### Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `INITIAL_ADMIN_PASSWORD` | Password for initial admin user | Random (check logs) |
| `WS_ALLOWED_ORIGINS` | WebSocket allowed origins (production) | `http://localhost:8080` |
| `CORS_ORIGINS` | CORS origins for HTTP API | See `main.py` |

### Model YAML

Standard [vLLM engine args](https://docs.vllm.ai/en/stable/configuration/engine_args/) plus dashboard-specific fields:

```yaml
# vLLM args (passed to engine)
model: Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8
served_model_name: Qwen3-Coder-30B
tensor_parallel_size: 2
max_model_len: 262144

# Dashboard fields (stripped before passing to vLLM)
model_type: moe_fp8                          # See Model Types below
vllm_image: vllm/vllm-openai:latest          # Override compose default
env_vars:                                    # Per-model env overrides
  VLLM_ATTENTION_BACKEND: FLASH_ATTN
```

### Model Types

Auto-detected from HuggingFace `config.json` or set explicitly:

| Type | Architecture | Quantization |
|------|--------------|--------------|
| `dense_full` | Dense | Full precision (FP16/BF16) |
| `dense_fp8` | Dense | FP8 |
| `dense_int8` | Dense | INT8 |
| `dense_int4` | Dense | INT4/AWQ |
| `moe_full` | Mixture of Experts | Full precision |
| `moe_fp8` | Mixture of Experts | FP8 |
| `moe_fp4` | Mixture of Experts | FP4 |

Detection logic reads `num_local_experts`, `quantization_config.quant_method`, and `weights.type`/`num_bits` from the model's `config.json`.

### Environment Layering

On activation, `env.active` is built from layers (later overrides earlier):

```
env.active = env.hardware + env.{model_type} + env_vars
```

| File | Scope |
|------|-------|
| `env.hardware` | All models (NCCL tuning, CUDA arch) |
| `env.{model_type}` | Models of that type |
| `env_vars` in YAML | Single model |

### Tool Call Parsers

| Model Family | Parser |
|--------------|--------|
| Mistral / Devstral | `mistral` |
| Qwen3 Coder | `qwen3_coder` |
| Llama 3.x | `llama3_json` |
| Llama 4 | `llama4` |
| MiniMax M2 | `minimax_m2` |
| Generic | `hermes` |

## Authentication

Default: admin user created on first start. Set `INITIAL_ADMIN_PASSWORD` or check logs for generated password.

**Roles:**
- `viewer` — read-only access
- `operator` — start/stop/switch models
- `admin` — full access including user management

Users can change their own password in Settings.

## How It Works

When you click **Activate**:

1. Dashboard reads model YAML, strips dashboard fields (`model_type`, `vllm_image`, `env_vars`)
2. Writes remainder to `active.yaml`
3. Merges env layers into `env.active`
4. Runs `docker compose up -d --force-recreate` with image tag injected

**Reload Config** re-reads the YAML and restarts without changing the selected config.

**Model Deletion** removes the model directory, associated config YAMLs, and HuggingFace cache entries.

## API

<details>
<summary>Endpoints</summary>

**vLLM**

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/vllm/configs` | List configurations |
| GET | `/api/vllm/active` | Active configuration |
| POST | `/api/vllm/switch` | Activate a config |
| POST | `/api/vllm/reload` | Reload active config |
| GET | `/api/vllm/status` | Container status |
| POST | `/api/vllm/start` `/stop` `/restart` | Container lifecycle |

**Models**

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/models/available` | Downloaded models |
| POST | `/api/models/download` | Start download |
| DELETE | `/api/models/{path}` | Delete model + config |
| GET | `/api/models/validate/{name}` | Check HuggingFace |

**Config**

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/config/model/{name}` | Get model config |
| POST | `/api/config/save` | Save model config |

**Auth**

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/login` | Login |
| POST | `/api/auth/logout` | Logout |
| POST | `/api/auth/password` | Change password |
| GET | `/api/auth/users` | List users (admin) |
| POST | `/api/auth/users` | Create user (admin) |

**WebSocket:** `/ws/updates` — GPU metrics, system stats, container status (2s interval).

</details>

## Project Structure

```
backend/
  api/           Route handlers
  services/      VLLMService, ConfigService, HuggingFaceService,
                 DockerService, GPUService, DownloadManager, AuthService
  main.py        FastAPI app
frontend/
  src/components/  React components
  src/pages/       Dashboard, Models, Monitoring, Containers, Settings
  nginx.conf       Reverse proxy to backend
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Can't start/stop vLLM | Verify `/var/run/docker.sock` mounted and backend has GPU access |
| Config switch succeeds but vLLM doesn't restart | Host paths must be accessible inside backend container |
| Env changes not applied | Docker reads `env_file` at creation. Use dashboard actions (not `docker restart`) |
| GPU metrics not showing | Backend needs GPU access for pynvml |
| Model download stuck | Check `downloads.json`. Interrupted downloads appear as resumable |
| Wrong Docker image | Delete `active.image` to reset to compose default |

## Tech Stack

**Frontend:** React 18 · TypeScript · Tailwind CSS · Vite

**Backend:** Python 3.12 · FastAPI · Docker SDK · pynvml · huggingface-hub

## License

BSD-2-Clause
