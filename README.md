# vLLM Dashboard

A modern web-based dashboard for managing [vLLM](https://github.com/vllm-project/vllm) inference servers. Switch between model configurations, monitor GPU utilization, download models from HuggingFace, and control containers—all without terminal access.

![License](https://img.shields.io/badge/license-BSD--2--Clause-blue.svg)
![Python](https://img.shields.io/badge/python-3.12-blue.svg)
![React](https://img.shields.io/badge/react-18-blue.svg)
![TypeScript](https://img.shields.io/badge/typescript-5-blue.svg)

## Features

- **Configuration Switching** — Switch between different vLLM model configurations with one click
- **Real-time GPU Monitoring** — Live GPU metrics via WebSocket streaming (no polling)
- **Model Management** — Download models from HuggingFace Hub with revision selection
- **Container Control** — Start, stop, restart vLLM and related containers
- **YAML Config Editor** — Edit vLLM configuration files with syntax validation
- **Environment Editor** — Manage environment variables for hardware tuning and model optimization
- **Multi-GPU Support** — Per-GPU breakdown for temperature, memory, power, and utilization

## Screenshots

### Dashboard
The main dashboard shows vLLM server status, active model configuration, and quick controls for switching models.

### GPU Monitoring
Real-time GPU metrics streamed via WebSocket, with per-GPU breakdown for multi-GPU systems.

### Model Management
Browse downloaded models, validate configurations, and download new models from HuggingFace.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         vLLM Dashboard                              │
├─────────────────────────────────────────────────────────────────────┤
│  Frontend (React/TypeScript)    │  Backend (FastAPI/Python)         │
│  ├─ Vite build                  │  ├─ Docker management             │
│  ├─ Tailwind CSS                │  ├─ GPU monitoring (pynvml)       │
│  ├─ WebSocket client            │  ├─ HuggingFace Hub integration   │
│  └─ YAML editor (js-yaml)       │  └─ Config file management        │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
          ┌─────────────────┐            ┌─────────────────┐
          │   vllm-proxy    │            │      vllm       │
          │ (API Gateway)   │───────────▶│ (Inference)     │
          └─────────────────┘            └─────────────────┘
```

The dashboard manages a **single vLLM container** with switchable configurations. An optional proxy handles request transformations for models that require them (e.g., Mistral tool call format).

## Quick Start

### Prerequisites

- Docker with Compose plugin
- NVIDIA GPU(s) with drivers installed
- HuggingFace account (token required for gated models)

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/vllm-dashboard.git
cd vllm-dashboard
```

### 2. Create Configuration Directory

```bash
mkdir -p /path/to/vllm/configs
```

### 3. Create a Model Configuration

Create a YAML file for your model (e.g., `devstral.yaml`):

```yaml
# Devstral 24B - Dense coding model with tool use
model: mistralai/Devstral-Small-2-24B-Instruct-2512
host: 0.0.0.0
port: 8000
download_dir: /root/.cache/huggingface
dtype: bfloat16
tensor_parallel_size: 2
attention_backend: FLASHINFER
disable_custom_all_reduce: true
gpu_memory_utilization: 0.92
max_model_len: 131072
max_num_seqs: 16
max_num_batched_tokens: 16384
served_model_name: Devstral-Small-2-24B
swap_space: 8
enable_chunked_prefill: true
enable_prefix_caching: true
trust_remote_code: true
tool_call_parser: mistral
enable_auto_tool_choice: true
```

### 4. Create Docker Compose File

```yaml
services:
  vllm:
    image: vllm/vllm-openai:latest
    container_name: vllm
    restart: unless-stopped
    ipc: host
    shm_size: 2g
    volumes:
      - /path/to/models:/root/.cache/huggingface
      - /path/to/vllm/configs:/root/.cache/vllm/configs
    env_file:
      - /path/to/vllm/configs/env.active
    environment:
      - VLLM_API_KEY=${VLLM_API_KEY:-local}
      - HUGGING_FACE_HUB_TOKEN=${HUGGING_FACE_HUB_TOKEN:-}
    command: >-
      --config /root/.cache/vllm/configs/active.yaml
      --api-key ${VLLM_API_KEY:-local}
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ['0', '1']
              capabilities: [gpu]

  vllm-dashboard-backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: vllm-dashboard-backend
    restart: unless-stopped
    environment:
      - TZ=${TZ:-UTC}
      - HUGGING_FACE_HUB_TOKEN=${HUGGING_FACE_HUB_TOKEN:-}
      - VLLM_MODELS_DIR=/models
      - VLLM_CONFIG_DIR=/vllm-configs
      - VLLM_COMPOSE_PATH=/vllm-compose
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - /path/to/models:/models:ro
      - /path/to/vllm/configs:/vllm-configs
      - /path/to/compose:/vllm-compose:ro
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ['0']
              capabilities: [gpu]

  vllm-dashboard-frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: vllm-dashboard-frontend
    restart: unless-stopped
    depends_on:
      - vllm-dashboard-backend
    ports:
      - "8080:80"
```

### 5. Build and Start

```bash
docker compose build
docker compose up -d
```

### 6. Access the Dashboard

Open `http://localhost:8080` in your browser.

## Configuration

### Model Configuration Files

The dashboard manages YAML configuration files that vLLM reads at startup. Each file represents a different model or configuration variant.

#### Example: Qwen3 Coder (FP8 MoE)

```yaml
# Qwen3 Coder 30B - FP8 quantized MoE model
model: Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8
host: 0.0.0.0
port: 8000
download_dir: /root/.cache/huggingface
dtype: bfloat16
tensor_parallel_size: 2
attention_backend: FLASHINFER
disable_custom_all_reduce: true
gpu_memory_utilization: 0.90
max_model_len: 262144
max_num_seqs: 8
max_num_batched_tokens: 8192
served_model_name: Qwen3-Coder-30B-A3B-Instruct-FP8
swap_space: 8
enable_chunked_prefill: true
enable_prefix_caching: true
trust_remote_code: true
tool_call_parser: qwen3_coder
enable_auto_tool_choice: true
```

#### Example: Devstral (Dense Model)

```yaml
# Devstral 24B - Dense coding model with tool use
model: mistralai/Devstral-Small-2-24B-Instruct-2512
host: 0.0.0.0
port: 8000
download_dir: /root/.cache/huggingface
dtype: bfloat16
tensor_parallel_size: 2
attention_backend: FLASHINFER
disable_custom_all_reduce: true
gpu_memory_utilization: 0.92
max_model_len: 131072
max_num_seqs: 16
max_num_batched_tokens: 16384
served_model_name: Devstral-Small-2-24B
swap_space: 8
enable_chunked_prefill: true
enable_prefix_caching: true
trust_remote_code: true
tool_call_parser: mistral
enable_auto_tool_choice: true
```

### Configuration Options Reference

| Option | Description | Example |
|--------|-------------|---------|
| `model` | HuggingFace model ID | `mistralai/Devstral-Small-2-24B-Instruct-2512` |
| `dtype` | Data type for inference | `bfloat16`, `float16`, `auto` |
| `tensor_parallel_size` | Number of GPUs for tensor parallelism | `2` |
| `attention_backend` | Attention implementation | `FLASHINFER`, `FLASH_ATTN`, `XFORMERS` |
| `gpu_memory_utilization` | Fraction of GPU memory to use | `0.90` |
| `max_model_len` | Maximum sequence length | `131072` |
| `max_num_seqs` | Maximum concurrent sequences | `16` |
| `served_model_name` | Model name exposed via API | `Devstral-Small-2-24B` |
| `tool_call_parser` | Parser for function calling | `mistral`, `qwen3_coder`, `hermes` |
| `enable_auto_tool_choice` | Enable automatic tool selection | `true` |
| `enable_chunked_prefill` | Enable chunked prefill for long contexts | `true` |
| `enable_prefix_caching` | Cache common prefixes | `true` |

See [vLLM Engine Arguments](https://docs.vllm.ai/en/latest/serving/engine_args.html) for the complete list.

### Environment Files

Environment files control hardware-specific and model-type optimizations:

| File | Purpose | Editable |
|------|---------|----------|
| `env.hardware` | Hardware-specific settings (NCCL tuning) | Yes |
| `env.moe-fp8` | FP8 MoE model optimizations | Yes |
| `env.dense` | Dense model settings | Yes |
| `env.active` | Combined env vars (auto-generated) | No |

#### Example: env.hardware (Dual RTX PRO 6000 Blackwell via PCIe)

```bash
# NCCL configuration for dual GPUs via PCIe (no NVLink)
NCCL_ALGO=Ring
NCCL_PROTO=Simple
NCCL_MIN_NCHANNELS=4
NCCL_MAX_NCHANNELS=8
NCCL_BUFFSIZE=8388608
NCCL_P2P_LEVEL=PHB
NCCL_DEBUG=WARN
NCCL_IB_DISABLE=1

# CUDA architecture - set for your GPU
# 12.0 = Blackwell, 8.9 = Ada Lovelace, 8.0 = Ampere
TORCH_CUDA_ARCH_LIST=12.0
```

#### Example: env.moe-fp8

```bash
# FlashInfer MoE optimizations for FP8 models
VLLM_USE_FLASHINFER_MOE_FP8=1
VLLM_FLASHINFER_MOE_BACKEND=cutlass
```

### Model Type Auto-Detection

The dashboard automatically detects model type from the model name:

| Model name contains | Detected type | Env file used |
|---------------------|---------------|---------------|
| `fp8` + (`moe`/`a3b`/`coder`) | `moe_fp8` | `env.moe-fp8` |
| `a3b` or `moe` (any case) | `moe_fp8` | `env.moe-fp8` |
| Anything else | `dense` | `env.dense` |

When switching configs, `env.active` is regenerated by combining `env.hardware` + the detected model-type env file.

## API Reference

### vLLM Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/vllm/status` | GET | Get vLLM container status |
| `/api/vllm/configs` | GET | List available configurations |
| `/api/vllm/active` | GET | Get active configuration |
| `/api/vllm/switch` | POST | Switch to a different config |
| `/api/vllm/start` | POST | Start vLLM container |
| `/api/vllm/stop` | POST | Stop vLLM container |
| `/api/vllm/restart` | POST | Restart vLLM container |

### Environment Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/vllm/env` | GET | List environment files |
| `/api/vllm/env/{filename}` | GET | Get env file contents |
| `/api/vllm/env/{filename}` | PUT | Update env file |

### Model Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/models/list` | GET | List downloaded models |
| `/api/models/download` | POST | Download a model from HuggingFace |
| `/api/models/validate/{name}` | GET | Validate model exists on HF |
| `/api/models/revisions/{name}` | GET | Get available model revisions |

### Configuration Files

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/config/model/{model_name}` | GET | Get config for a model |
| `/api/config/model/{model_name}` | PUT | Update config for a model |

### Container Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/containers/list` | GET | List AI stack containers |
| `/api/containers/{name}/logs` | GET | Get container logs |
| `/api/containers/{name}/start` | POST | Start container |
| `/api/containers/{name}/stop` | POST | Stop container |
| `/api/containers/{name}/restart` | POST | Restart container |

### WebSocket

| Endpoint | Description |
|----------|-------------|
| `/ws/updates` | Real-time GPU metrics, system stats, container status |

WebSocket messages are JSON with this structure:

```json
{
  "type": "monitoring",
  "data": {
    "gpus": [
      {
        "index": 0,
        "name": "NVIDIA RTX PRO 6000",
        "temperature": 45,
        "memory_used": 42000,
        "memory_total": 98304,
        "power_draw": 150,
        "power_limit": 350,
        "utilization": 85
      }
    ],
    "system": {
      "cpu_percent": 15.2,
      "memory_percent": 45.8
    },
    "timestamp": "2025-01-20T10:30:00-08:00"
  }
}
```

## Project Structure

```
vllm-dashboard/
├── backend/
│   ├── api/
│   │   ├── config.py          # Configuration file endpoints
│   │   ├── containers.py      # Container management endpoints
│   │   ├── models.py          # Model management endpoints
│   │   ├── monitoring.py      # System monitoring endpoints
│   │   ├── vllm.py            # vLLM control endpoints
│   │   └── websockets.py      # WebSocket streaming
│   ├── services/
│   │   ├── config_service.py  # Config file operations
│   │   ├── docker_service.py  # Docker interaction
│   │   ├── gpu_service.py     # GPU monitoring via pynvml
│   │   ├── hf_service.py      # HuggingFace Hub client
│   │   └── vllm_service.py    # vLLM container management
│   ├── Dockerfile
│   ├── main.py
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── common/        # Reusable UI components
│   │   │   ├── containers/    # Container management UI
│   │   │   ├── layout/        # Dashboard layout
│   │   │   ├── models/        # Model management UI
│   │   │   ├── monitoring/    # GPU monitoring UI
│   │   │   └── vllm/          # vLLM control UI
│   │   ├── pages/             # Route pages
│   │   ├── services/          # API clients
│   │   └── types/             # TypeScript types
│   ├── Dockerfile
│   ├── nginx.conf
│   ├── package.json
│   └── vite.config.ts
└── README.md
```

## Tech Stack

### Backend
- **Python 3.12** — Runtime
- **FastAPI** — Web framework
- **docker** — Docker SDK for Python
- **pynvml** — NVIDIA GPU monitoring
- **huggingface-hub** — Model downloads
- **PyYAML** — Configuration parsing

### Frontend
- **React 18** — UI framework
- **TypeScript** — Type safety
- **Vite** — Build tool
- **Tailwind CSS** — Styling
- **Recharts** — Charts and graphs
- **js-yaml** — YAML parsing in browser

## Optional: vLLM Proxy

For models that require request transformations (e.g., Mistral's tool call format), you can add an API proxy:

```yaml
vllm-proxy:
  build:
    context: ./vllm-proxy
    dockerfile: Dockerfile
  container_name: vllm-proxy
  restart: unless-stopped
  environment:
    - VLLM_URL=http://vllm:8000
    - LOG_LEVEL=INFO
  depends_on:
    - vllm
```

The proxy handles:
- Removing `index` field from tool calls (vLLM rejects it)
- Converting array content to string in tool messages
- Reordering messages for Mistral tokenizer compatibility

For models that don't need transformations (e.g., Qwen), the proxy acts as a transparent passthrough.

## Troubleshooting

### vLLM won't start

```bash
docker logs vllm --tail 100
```

Common issues:
- **Invalid YAML** — Check config file syntax
- **Insufficient GPU memory** — Lower `gpu_memory_utilization` or `max_model_len`
- **Model not downloaded** — Use the Models page to download first

### Dashboard can't connect to Docker

```bash
docker logs vllm-dashboard-backend --tail 50
```

Verify:
- Docker socket is mounted: `-v /var/run/docker.sock:/var/run/docker.sock`
- Backend has proper permissions

### GPU metrics not showing

- Verify `nvidia-smi` works on host
- Check backend container has GPU access in compose.yaml
- Review pynvml initialization in backend logs

### WebSocket disconnects

The frontend automatically reconnects. If issues persist:
- Check backend is running and healthy
- Verify no firewall blocking WebSocket connections
- Check browser console for errors

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

BSD-2-Clause License — see [LICENSE](LICENSE) for details.

## Acknowledgments

- [vLLM](https://github.com/vllm-project/vllm) — High-throughput LLM serving
- [HuggingFace](https://huggingface.co) — Model hub and libraries
- [FastAPI](https://fastapi.tiangolo.com) — Modern Python web framework
- [Tailwind CSS](https://tailwindcss.com) — Utility-first CSS
