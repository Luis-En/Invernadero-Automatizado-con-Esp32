# VS Code setup

The project ships a multi-root workspace so the firmware, backend and frontend
can be opened and edited together.

## Open the project

1. Install [Visual Studio Code](https://code.visualstudio.com/).
2. Open the workspace file:

   ```bash
   code /home/luis/Proyectos/InvernaderoAuto/invernaderoauto.code-workspace
   ```

   Or use **File > Open Workspace from File...** and pick
   `invernaderoauto.code-workspace`.

VS Code will offer the recommended extensions on first open (see
`.vscode/extensions.json`). Accept them.

## Extensions

| Extension | Purpose |
|-----------|---------|
| `platformio.platformio-ide` | Build/flash/monitor the ESP32 firmware |
| `ms-python.python` + `vscode-pylance` + `debugpy` | Backend edit, run, debug, test |
| `dbaeumer.vscode-eslint` + `esbenp.prettier-vscode` | Frontend lint/format |
| `ms-azuretools.vscode-docker` | Manage the compose stack |
| `bierner.markdown-mermaid` | Render the architecture diagrams |
| `humao.rest-client` | Run `docs/api.http` requests |
| `redhat.vscode-yaml` | Validate `config/*.yaml` |

The PlatformIO IDE extension bundles its own PlatformIO Core, so a separate
`pip install platformio` is not required for VS Code builds.

## Python environment (backend)

Create an interpreter for the backend so Pylance, pytest and the debugger work:

```bash
cd backend/api
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

`.vscode/settings.json` already points at `backend/api/.venv/bin/python`.

## Tasks

Run with **Terminal > Run Task...** (or `Ctrl+Shift+P` then "Run Task"):

| Task | What it does |
|------|--------------|
| Firmware: build field | `pio run -e field` |
| Firmware: build gateway | `pio run -e gateway` |
| Firmware: build camera | `pio run -e camera` |
| Firmware: build all | builds the three nodes in sequence |
| Firmware: upload field / gateway / camera | flash a board |
| Firmware: field logic tests (host) | compiles and runs `tools/logic_tests.cpp` |
| Firmware: gateway payload validation | validates the JSON payloads |
| Backend: run tests | `pytest tests -q` |
| Frontend: dev server | `npm run dev` |
| Frontend: build / lint | production build, ESLint |
| Docker: up / down / logs | manage the Raspberry Pi stack locally |

`Firmware: build field` is the default build task (`Ctrl+Shift+B`).
`Backend: run tests` and `Firmware: field logic tests` are the default test
tasks.

## Debugging

**Run and Debug** (`Ctrl+Shift+D`) offers:

| Configuration | Use |
|---------------|-----|
| Backend: FastAPI (uvicorn) | run the API with breakpoints |
| Backend: pytest | debug the test suite |
| Serial bridge: simulator | debug the simulator against a running API |
| Frontend: Chrome | debug the React app with source maps |

The **Backend + Frontend** compound starts the API and opens Chrome in one go.
For the backend/frontend configurations, start the Docker stack first (task
**Docker: up**) or run the pieces natively.

## IntelliSense for firmware

PlatformIO resolves headers per project, so open one firmware folder at a time
for the most accurate C++ IntelliSense. In the multi-root workspace each node
is its own folder, and `.vscode/settings.json` sets the C++ standard to
`gnu++17` to match `platformio.ini`.

## Serial monitor

Use the PlatformIO toolbar (plug icon) or:

```bash
pio device monitor -e field
```

`monitor_filters = esp32_exception_decoder` is enabled so a panic prints a
readable backtrace instead of raw addresses.
