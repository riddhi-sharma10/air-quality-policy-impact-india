"""Run the whole analysis notebook from the final dataset and write the executed copy.

Usage (from the repository root):
    python run_all.py --from-final
    python run_all.py --from-final --notebook notebooks/air_quality_policy_impact.ipynb --output outputs/executed_notebook.ipynb

What it does: runs every code cell of the notebook in order in one fresh Python process (the same as Restart and run all), with the working
folder set to notebooks/. Every figure (PNG and SVG) goes to outputs/figures, every table to outputs/tables, and the station-day analysis tables
to data/processed/analysis_*.parquet. The executed copy, with all outputs stored, is written to --output; the source notebook is not changed.
The input is data/processed/final_dataset.parquet (git-ignored; see README.md for how it is built). Needs: numpy, pandas, matplotlib, seaborn,
statsmodels, patsy, scikit-learn, pyarrow, nbformat, IPython; shap is optional (a cell skips it if it is missing).
"""
import argparse, base64, builtins, contextlib, io, os, sys, time

ROOT = os.path.dirname(os.path.abspath(__file__))
parser = argparse.ArgumentParser(description="Run the analysis notebook from the final dataset.")
parser.add_argument("--from-final", action="store_true", help="start from data/processed/final_dataset.parquet (the only supported start)")
parser.add_argument("--notebook", default=os.path.join("notebooks", "air_quality_policy_impact.ipynb"))
parser.add_argument("--output", default=os.path.join("outputs", "executed_notebook.ipynb"))
args = parser.parse_args()
if not args.from_final:
    sys.exit("Use --from-final: the run starts from data/processed/final_dataset.parquet.")
parquet = os.path.join(ROOT, "data", "processed", "final_dataset.parquet")
if not os.path.exists(parquet):
    sys.exit(f"Missing {parquet}. The final table is git-ignored: build it with the scripts in src/ (see README.md) or copy it there.")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import nbformat
import IPython.display as ipd
from IPython.core.interactiveshell import InteractiveShell
from nbformat.v4 import new_output

nb_path, out_path = os.path.join(ROOT, args.notebook), os.path.join(ROOT, args.output)
os.makedirs(os.path.dirname(out_path), exist_ok=True)
os.chdir(os.path.join(ROOT, "notebooks"))                       # the notebook is written to run from notebooks/ or from the root
nb = nbformat.read(nb_path, as_version=4)
shell, outputs, buf = InteractiveShell.instance(), [], io.StringIO()


def flush_stream():
    if buf.getvalue():
        outputs.append(new_output("stream", name="stdout", text=buf.getvalue()))
        buf.seek(0); buf.truncate(0)


def show_object(*objs, **kwargs):
    flush_stream()
    for obj in objs:
        data, meta = shell.display_formatter.format(obj)
        outputs.append(new_output("display_data", data=data, metadata=meta))


def show_figures(*a, **k):
    flush_stream()
    for number in plt.get_fignums():
        png = io.BytesIO(); plt.figure(number).savefig(png, format="png", dpi=100, bbox_inches="tight")
        outputs.append(new_output("display_data", data={"image/png": base64.b64encode(png.getvalue()).decode(), "text/plain": "<Figure>"}, metadata={}))
    plt.close("all")


ipd.display = show_object; builtins.display = show_object; plt.show = show_figures
namespace, start, count = {"__name__": "__main__"}, time.time(), 0
for index, cell in enumerate(nb.cells):
    if cell.cell_type != "code":
        continue
    count += 1; outputs.clear(); buf.seek(0); buf.truncate(0)
    try:
        with contextlib.redirect_stdout(buf):
            exec(compile(cell.source, f"cell{index}", "exec"), namespace)
    except Exception:
        flush_stream(); print(f"Stopped in cell {index}, step: {cell.source.splitlines()[0][:100]}", file=sys.stderr)
        print("".join(o.get("text", "") for o in outputs)[-1500:], file=sys.stderr); raise
    flush_stream(); cell.outputs = list(outputs); cell.execution_count = count
nbformat.validate(nb); nbformat.write(nb, out_path)
print(f"ran {count} code cells in {(time.time() - start) / 60:.1f} min; executed copy: {out_path}")
