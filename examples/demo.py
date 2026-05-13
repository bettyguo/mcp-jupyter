"""End-to-end demo driver against a real Python kernel, no Jupyter server.

Drives a standalone session through the tool sequence an agent would
typically use against the sample notebook fixture and prints what the
agent would see as a markdown transcript.

Usage:
    python examples/demo.py [--notebook PATH]
"""

from __future__ import annotations

import asyncio
import json
import shutil
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from mcp_jupyter_kernel.config import StandaloneConfig  # noqa: E402
from mcp_jupyter_kernel.helpers.bootstrap import helper_call  # noqa: E402
from mcp_jupyter_kernel.jupyter.standalone import StandaloneSession  # noqa: E402
from mcp_jupyter_kernel.tools.kernel_ import _parse_helper_output  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "sample_notebook.ipynb"


def md_section(title: str) -> None:
    print(f"\n## {title}\n")


def md_call(name: str, args: dict) -> None:
    print(f"**`{name}({', '.join(f'{k}={v!r}' for k, v in args.items())})`**")


def md_result(label: str, value: object) -> None:
    print(f"\n_{label}:_\n")
    print("```json")
    print(json.dumps(value, indent=2, default=str)[:1800])
    print("```\n")


async def main(notebook_path: Path) -> int:
    tmpdir = Path(tempfile.mkdtemp(prefix="mjk-demo-"))
    work_nb = tmpdir / "customer_analysis.ipynb"
    shutil.copyfile(notebook_path, work_nb)

    print("# mcp-jupyter-kernel demo transcript")
    print()
    print(f"Working notebook: `{work_nb.name}`")

    session = StandaloneSession(
        StandaloneConfig(kernel_name="python3", notebook_path=str(work_nb))
    )
    await session.start()

    try:
        # Bring the notebook to the state it would be in if the user had
        # already stepped through the setup cells in Lab.
        md_section("Setup: run the existing cells so customer_df is in scope")
        for cell_index in range(4):
            await session.execute_cell("local", cell_index=cell_index, timeout_s=30)
        print("Cells 0-3 executed; `customer_df` is now in the kernel.")

        md_section("notebooks.list_open")
        md_call("notebooks.list_open", {})
        handles = await session.list_notebooks()
        md_result(
            "result",
            [
                {
                    "notebook_id": h.notebook_id,
                    "path": h.path,
                    "kernel_id": h.kernel_id[:8] + "...",
                    "kernel_status": h.kernel_status,
                }
                for h in handles
            ],
        )

        nb_id = handles[0].notebook_id

        md_section("cells.read_recent")
        md_call("cells.read_recent", {"notebook_id": nb_id, "n": 5})
        cells = await session.read_cells(nb_id, n=5)
        compact = [
            {
                "index": c["index"],
                "cell_type": c["cell_type"],
                "source_preview": c["source"][:80] + ("..." if len(c["source"]) > 80 else ""),
                "execution_count": c.get("execution_count"),
            }
            for c in cells
        ]
        md_result("result", compact)

        md_section("inspect('customer_df', mode='auto')")
        md_call("inspect", {"target": "customer_df", "mode": "auto"})
        r = await session.execute_code(
            nb_id, helper_call("inspect_auto", "customer_df"), timeout_s=15
        )
        auto = _parse_helper_output(r.outputs)
        md_result("result", auto)

        md_section("inspect('customer_df', mode='summary')")
        md_call("inspect", {"target": "customer_df", "mode": "summary"})
        r = await session.execute_code(
            nb_id, helper_call("inspect_summary", "customer_df"), timeout_s=15
        )
        summary = _parse_helper_output(r.outputs)
        if isinstance(summary, dict) and isinstance(summary.get("value_counts"), dict):
            summary["value_counts"] = {
                k: v for k, v in list(summary["value_counts"].items())[:2]
            }
        md_result("result (excerpt)", summary)

        md_section("Insert and execute a plot cell")
        plot_code = (
            "get_ipython().run_line_magic('matplotlib', 'inline')\n"
            "import matplotlib.pyplot as plt\n"
            "fig, ax = plt.subplots(figsize=(6, 4))\n"
            "customer_df.groupby('country')['mrr'].sum().sort_values().plot.barh(ax=ax)\n"
            "ax.set_title('Total MRR by country')\n"
            "from IPython.display import display\n"
            "display(fig)\n"
            "plt.close(fig)\n"
        )
        live_cells = await session.read_cells(nb_id, n=1000)
        after = len(live_cells) - 1
        md_call(
            "cells.insert",
            {"notebook_id": nb_id, "after_index": after, "code": "<plot code>"},
        )
        new_idx = await session.insert_cell(nb_id, after_index=after, code=plot_code)
        print(f"\n_Inserted at index_: {new_idx}\n")
        md_call("execute.cell", {"notebook_id": nb_id, "cell_index": new_idx, "timeout_s": 30})
        r = await session.execute_cell(nb_id, cell_index=new_idx, timeout_s=30)
        print(f"\n_status_: `{r.status}` _(wall {r.wall_time_ms} ms)_\n")

        md_section("plots.capture_last")
        md_call("plots.capture_last", {"notebook_id": nb_id})
        plot = session.get_last_plot()
        if plot:
            png_len = len(plot["image_png_base64"])
            md_result(
                "result",
                {
                    "source": plot["source"],
                    "image_png_base64": f"<{png_len} chars; b64 PNG; starts {plot['image_png_base64'][:24]}...>",
                },
            )
        else:
            md_result("result", None)

        return 0
    finally:
        await session.close()
        shutil.rmtree(tmpdir, ignore_errors=True)


def cli() -> None:
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--notebook", default=str(FIXTURE))
    args = p.parse_args()
    raise SystemExit(asyncio.run(main(Path(args.notebook))))


if __name__ == "__main__":
    cli()
