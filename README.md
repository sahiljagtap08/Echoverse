<div align="center">

# Echoverse: Deep, Evolving Environments for Computer-Use Agents

*Deep, behaviorally faithful web environments for training and evaluating computer-use agents.*

<a href="https://arxiv.org/abs/2607.28074"><img src="https://img.shields.io/badge/Paper-arXiv-b31b1b" alt="Paper"></a>
<a href="https://aka.ms/echoverse-techreport"><img src="https://img.shields.io/badge/Blog-Post-6f42c1" alt="Blog"></a>
<a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue" alt="License"></a>

</div>

---

<div align="center">

https://github.com/user-attachments/assets/9dace361-bdac-43f8-a5d3-bc778162520b

</div>

**Echoverse** is an environment *factory* for computer-use agents: instead of scaling the
raw count of synthetic websites, it scales the **fidelity, depth, and correctness** inside each
one. A world here is more than a rendered page — it is real, resettable state, the actions that
change it, the consequences they produce, and a **database-grounded verifier** that checks the
outcome. The factory produces two kinds of world:

- **Full-domain worlds** (the **Echo family**) — rich, realistic workflows that
  preserve the causal structure of real work (shared threads, permissions, audit histories,
  consequential writes).
- **Capability worlds** — narrow worlds that drill a single control (e.g. a date picker or a
  nested filter) across many layouts, so an agent learns the *skill*, not one screen.

This repository is a **public release of a subset** of that factory: **four environments** with
their **test task sets**, plus a small standalone **[harness](harness/README.md)** that launches
an environment for a task, runs many instances concurrently, and verifies agent outcomes. For the motivation, methodology, and results, see the [blog post](https://aka.ms/echoverse-techreport).

Each environment is a self-contained **FastAPI backend + Vite/React frontend + SQLite** app that
serves a realistic web UI an agent can drive. Tasks are graded by an **LLM judge** over an
OpenAI-compatible API.

## Environments

Echoverse ships **four environments** — two full-domain worlds and two capability skills.
Each capability skill has an **in-distribution** and an **out-of-distribution** split, so the
tasks are organized into **six splits** (the six rows below):

```
Echoverse
├── Full-domain worlds
│   ├── echostay              lodging marketplace
│   └── echoforge             developer collaboration / code hosting
└── Capability skills
    ├── date pickers
    │   ├── datepickers       in-distribution
    │   └── datepickers_ood   out-of-distribution
    └── nested filters
        ├── nested_filter     in-distribution
        └── nested_filter_ood out-of-distribution
```

The **in-distribution** split covers the widget types, layouts, and target values a skill is
expected to have seen; the **out-of-distribution** (`_ood`) split holds out **novel** widget
types, families, and scenarios the in-distribution set does not cover. Comparing the two measures
whether an agent has learned the underlying *skill* and generalizes to unseen layouts, rather than
memorizing specific screens — the gap between the columns in the [reference results](#reference-results-fara15-9b-vs-fara15-4b) below.

| Environment | Kind | Port | Tasks | Grounding DB | Description |
|---|---|---|---|---|---|
| [`echostay`](envs/echostay) | Full domain | 8000 | 117 | [`echostay.db`](https://huggingface.co/datasets/microsoft/Echoverse/blob/main/echostay/echostay.db) · 21 MB | Lodging marketplace (search, listings, bookings, wishlists) |
| [`echoforge`](envs/echoforge) | Full domain | 8051 | 101 | [`echoforge.db`](https://huggingface.co/datasets/microsoft/Echoverse/blob/main/echoforge/echoforge.db) · 344 MB | Developer collaboration / code hosting (projects, issues, merge requests) |
| [`datepickers`](envs/datepickers) | Capability | 5400 | 109 | [`datepicker_grounded.db`](https://huggingface.co/datasets/microsoft/Echoverse/blob/main/datepickers/datepicker_grounded.db) · 3.6 MB | Date-picker widgets (in-distribution) |
| [`datepickers_ood`](envs/datepickers_ood) | Capability | 5401 | 150 | [`datepicker_ood_grounded.db`](https://huggingface.co/datasets/microsoft/Echoverse/blob/main/datepickers_ood/datepicker_ood_grounded.db) · 1.0 MB | Date-picker widgets (out-of-distribution) |
| [`nested_filter`](envs/nested_filter) | Capability | 5500 | 100 | [`nested_filter.db`](https://huggingface.co/datasets/microsoft/Echoverse/blob/main/nested_filter/nested_filter.db) · 172 KB | Nested / faceted-filter widgets (in-distribution) |
| [`nested_filter_ood`](envs/nested_filter_ood) | Capability | 5501 | 145 | [`nested_filter_ood.db`](https://huggingface.co/datasets/microsoft/Echoverse/blob/main/nested_filter_ood/nested_filter_ood.db) · 104 KB | Nested / faceted-filter widgets (out-of-distribution) |

Ports are the per-env script defaults; the harness assigns free ports automatically so many
instances can run at once. **The grounding databases are not committed to git** — the test tasks
ship in this repo under `envs/<env>/tasks/`, but each `.db` is distributed via the Hugging Face
dataset **[microsoft/Echoverse](https://huggingface.co/datasets/microsoft/Echoverse)**. Install the
CLI and pull all six into place, **from the repository root**:

```bash
pip install -U huggingface_hub          # provides the `hf` CLI
hf download microsoft/Echoverse --repo-type dataset --include "*/*.db" --local-dir ./envs
```

This lands each DB at `envs/<env>/<grounding>.db`, where the launcher expects it. For a single env,
name its file — e.g. `hf download microsoft/Echoverse echostay/echostay.db --repo-type dataset --local-dir ./envs`.

> The full Echoverse domain suite is the **ten-environment Echo family** (EchoMail,
> EchoCalendar, EchoChat, EchoML, EchoForge, EchoBank, EchoCare, EchoForum, EchoTunes, EchoStay).
> This repository releases **EchoStay** and **EchoForge** plus the two capability worlds.

## Quick Start

Install the harness (core deps: `openai`, `requests`, `python-dotenv`, `azure-identity`):

```bash
pip install -e harness
```

**Run an environment for a task** — copies the seed DB, launches backend + frontend on free
ports, and prints the URL your agent should drive:

```bash
python -m harness.run_env --env nested_filter \
    --task W01_E03_G011 --output-dir ./runs/W01_E03_G011
# ... drive your own agent at the printed URL ...
# Ctrl-C to tear down; the post-run DB lands in ./runs/W01_E03_G011/final_db_state.db
```

**Verify the result** — the judge reads its endpoint/credentials from the environment or a
repo-root `.env` (see [harness/README.md](harness/README.md#configuring-credentials-env)):

```bash
python -m harness.verify_cli --env nested_filter --task W01_E03_G011 \
    --final-db ./runs/W01_E03_G011/final_db_state.db
```

The judge works with OpenAI, Azure OpenAI (API key), or Azure OpenAI with Azure AD credentials
(`az login` / managed identity) — auto-detected, or forced with `--auth`.

You bring your own agent — the harness only launches the environment and grades the outcome. See
**[harness/README.md](harness/README.md)** for the full API, running many instances concurrently,
and per-family grading details.

### Run with Fara1.5 (optional reference agent)

Don't have an agent handy? The harness ships an optional **reference agent** that drives the
environments with Microsoft's released **[Fara1.5](https://github.com/microsoft/fara)** computer-use
models — launch → drive → capture → grade, with no agent code to write. It's the worked example of
the harness's pluggable **agent seam** (`--agent`):

```bash
pip install -e "harness[fara]"        # public microsoft/fara (+ Playwright); needs Python >= 3.11
python -m playwright install chromium

# serve a model (weights are public on Hugging Face — auto-downloaded on first run):
CUDA_VISIBLE_DEVICES=0 bash scripts/serve_fara15.sh 9b     # 4b / 9b / 27b

# run + grade one task:
python -m harness.run_agent --agent fara15 --env datepickers --task dpg_0008 \
    --output-dir ./runs/dpg_0008 --verify
```

`fara` is an optional extra (the core harness stays agent-agnostic — bring your own agent by adding
`harness/agents/<name>.py`). Model-weight download, serving (incl. multi-GPU for 27B), the agent
seam, and all runner options are documented in
**[harness/README.md → Run with Fara1.5](harness/README.md#run-with-fara15-reference-agent)**.

### Reference results: Fara1.5-9B vs Fara1.5-4B

Pass rate of Microsoft's released Fara1.5 computer-use models on all six Echoverse environments
(722 tasks total), graded by the LLM judge. Both runs used the public weights served with vLLM on
4× A100 (9B at global task concurrency 16, 4B at 32).

| Environment | Tasks | Fara1.5-9B | Fara1.5-4B |
|---|---:|---:|---:|
| `datepickers` | 109 | 87.2% (95/109) | 82.6% (90/109) |
| `datepickers_ood` | 150 | 63.3% (95/150) | 46.0% (69/150) |
| `echoforge` | 101 | 38.6% (39/101) | 35.6% (36/101) |
| `echostay` | 117 | 59.8% (70/117) | 54.7% (64/117) |
| `nested_filter` | 100 | 91.0% (91/100) | 78.0% (78/100) |
| `nested_filter_ood` | 145 | 87.6% (127/145) | 82.1% (119/145) |
| **Overall** | **722** | **71.6% (517/722)** | **63.2% (456/722)** |

Models are Microsoft's publicly released, ungated Fara1.5 weights on Hugging Face (auto-downloaded
on first serve): **[microsoft/Fara1.5-4B](https://huggingface.co/microsoft/Fara1.5-4B)**,
**[microsoft/Fara1.5-9B](https://huggingface.co/microsoft/Fara1.5-9B)**, and
**[microsoft/Fara1.5-27B](https://huggingface.co/microsoft/Fara1.5-27B)** — see the
[Fara project](https://github.com/microsoft/fara) for model details.

## Verification

Every task carries its own answer key — a looked-up value or a state change **minted from the
environment's real database** — so success is a property of the app's own state, not a model's
read of a screenshot. Tasks are graded by an **LLM judge** over an OpenAI-compatible
API: read tasks compare the agent's answer to the reference value, write tasks compare the
database diff to the expected state change, and the judge only absorbs UI fuzz (rounding,
formatting, wording).

## Prerequisites

- **Python 3.10+** and **[uv](https://docs.astral.sh/uv/)**
- **Node.js 18+** (for the environment frontends)
- **`sqldiff`** (from the [SQLite tools bundle](https://www.sqlite.org/download.html)) — for
  LLM write-task verification (`apt install sqlite3-tools` / `brew install sqlite`)
- **LLM credentials** for the verifier — an OpenAI-compatible endpoint configured via the
  environment or a repo-root `.env` (OpenAI API key, Azure OpenAI API key, or Azure AD via
  `DefaultAzureCredential`). See [harness/README.md](harness/README.md#configuring-credentials-env).

## Repository structure

```
envs/                 # the released environments (backend/ + frontend/ + tasks + README)
  echostay/           #   full-domain world — lodging marketplace
  echoforge/          #   full-domain world — developer collaboration / code hosting
  datepickers/        #   capability world — date pickers (in-distribution)
  datepickers_ood/    #   capability world — date pickers (out-of-distribution)
  nested_filter/      #   capability world — nested filters (in-distribution)
  nested_filter_ood/  #   capability world — nested filters (out-of-distribution)
harness/              # standalone launcher + verifier (see harness/README.md)
```

## Attribution

Worlds are named for the **workflow** they represent. **EchoStay** (a lodging marketplace) and
**EchoForge** (developer collaboration / code hosting) are the two full-domain worlds; the
capability worlds are original. Their grounding data comes from public sources:

- **EchoStay** — seed data adapted from [InsideAirbnb](http://insideairbnb.com/) (© InsideAirbnb),
  licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The data was modified to
  generate synthetic listing, host, review, and location seeds.
- **EchoForge** — data derived from the [WebArena](https://github.com/web-arena-x/webarena) corpus,
  licensed under the [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0).

All product names and trademarks referenced are the property of their respective owners and are used
for identification purposes only. See each environment's README for details on its data sources.

## Responsible AI

These environments and tasks are released for **research purposes** — they are fictional, synthetic
worlds for research on and evaluation of computer-use agents, and are not affiliated with or endorsed
by any third party. Before using them, please read the [Transparency Note](TRANSPARENCY.md), which
describes intended uses, out-of-scope uses, limitations, and best practices.

## Contributing

This project welcomes contributions and suggestions. Most contributions require you to agree to a
Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us
the rights to use your contribution. For details, visit https://cla.opensource.microsoft.com.

This project has adopted the [Microsoft Open Source Code of Conduct](CODE_OF_CONDUCT.md). For more
information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or
contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or
comments.

## Trademarks

This project may contain trademarks or logos for projects, products, or services. Authorized use
of Microsoft trademarks or logos is subject to and must follow
[Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/en-us/legal/intellectualproperty/trademarks/usage/general).
Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion
or imply Microsoft sponsorship. Any use of third-party trademarks or logos are subject to those
third-party's policies.

## License

Released under the [MIT License](LICENSE). See [SECURITY.md](SECURITY.md) for security reporting.

## Citation

```bibtex
@misc{echoverse,
      title={Echoverse: Deep, Evolving Environments for Training Computer-Use Agents at Scale},
      author={Yash Pandya and Sahil Gupta and Sarthak Harne and Archana Yadav and Kavyansh Chourasia and Hussein Mozannar and Vibhav Vineet and Sara Abdali and Corby Rosset and Yash Lara and Ahmed Awadallah and Ece Kamar and Akshay Nambi},
      year={2026},
      url={https://aka.ms/echoverse-techreport},
}
```
