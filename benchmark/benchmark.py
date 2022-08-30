# flake8: noqa: E402
import argparse
import bz2
import csv
import datetime
import json
import os
import sys
from io import StringIO
from pathlib import Path
from matplotlib import pyplot as plt

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(SCRIPT_DIR))

from eyecite import get_citations, clean_text

csv.field_size_limit(sys.maxsize)

root = Path(__file__).parent.absolute()

MAX_ROWS_IN_MD = 51


class Benchmark(object):
    """Benchmark the different eyecite branches"""

    def get_filepath(self, filename):
        return Path.joinpath(root, filename)

    def generate_branch_report(self, branch: str) -> None:
        """Generate Report

        :param branch: Is a branch from main or not
        :return: None
        """
        zipfile = bz2.BZ2File(self.get_filepath("bulk-file.csv.bz2"))
        csv_data = csv.DictReader(
            StringIO(zipfile.read().decode()), delimiter=","
        )
        count = 0
        now = datetime.datetime.now()
        data = []
        for row in csv_data:
            output = {}
            id = row.pop("id")
            newrow = {k: v for k, v in row.items() if v}
            found_citations = get_citations(
                clean_text(
                    list(newrow.values())[0], ["html", "inline_whitespace"]
                )
            )
            cites = [cite.token.data for cite in found_citations if cite.token]
            count += len(cites)
            output["id"] = id
            output["cites"] = cites
            output["total"] = count
            output["time"] = (datetime.datetime.now() - now).total_seconds()
            data.append(output)
        with open(self.get_filepath(f"{branch}.json"), "w") as f:
            json.dump(data, fp=f, indent=4)

    def write_report(self, repo, pr_number):
        """Begin building Report.MD file

        :return: None
        """
        max_gain, max_loss = 6, 6
        gains, losses = 0, 0
        with open("benchmark/output.csv", mode="r") as inp:
            reader = csv.DictReader(inp)
            for row in reader:
                if row["Gain"]:
                    gains += 1
                    max_gain = (
                        len(row["Gain"])
                        if len(row["Gain"]) > max_gain
                        else max_gain
                    )
                if row["Loss"]:
                    losses += 1
                    max_loss = (
                        len(row["Loss"])
                        if len(row["Loss"]) > max_loss
                        else max_loss
                    )

        with open(self.get_filepath("report.md"), "w") as f:
            f.write("# The Eyecite Report :eye:\n\n")
            f.write("\n\nGains and Losses\n")
            f.write("---------\n")
            f.write(f"There were {gains} gains and " f"{losses} losses.\n")
            f.write("\n<details>\n")
            f.write("<summary>Click here to see details.</summary>\n\n")

            if max_gain + max_loss > MAX_ROWS_IN_MD:
                f.write(
                    f"There were {max_gain + max_loss} changes so we are only "
                    f"displaying the first 50. You can review the \n"
                    f"entire list by downloading the output.csv "
                    f"file linked above.\n\n"
                )
            # Generate Markdown Table of Outputs up to 50 rows.
            row_count = 0
            with open("benchmark/output.csv", mode="r") as inp:
                reader = csv.DictReader(inp)
                header = [
                    "id".center(10),
                    "Gain".center(max_gain),
                    "Loss".center(max_loss),
                ]
                f.write(f"| {' | '.join(header)} |\n")
                blank = ["-" * 10, "-" * max_gain, "-" * max_loss]
                f.write(f"| {' | '.join(blank)} |\n")
                for row in reader:
                    table = []
                    for value, whitespace_adjust in zip(
                        list(row.values()), [10, max_gain, max_loss]
                    ):
                        table.append(value.center(whitespace_adjust))
                    f.write(f"| {' | '.join(table)} |\n")
                    row_count += 1
                    if row_count > MAX_ROWS_IN_MD:
                        break

        with open(self.get_filepath("report.md"), "a+") as f:
            f.write("\n\n</details>\n\n")

        # Add header for time chart for PR comment
        with open(self.get_filepath("report.md"), "a") as f:
            f.write("\n\nTime Chart\n")
            f.write("---------\n")

        with open(self.get_filepath("report.md"), "a") as f:
            # Add Link to Repository Chart image
            link = f"\n![image](https://raw.githubusercontent.com/{repo}/artifacts/{pr_number}/results/chart.png)\n"
            f.write(link)

    def append_links(self, branch1, branch2, pr_number, repo):
        """Add links to output in PR document report

        :param branch1: Main branch name
        :param branch2: Updated branch name
        :param pr_number: PR # trigger
        :param repo: The repository to upload to
        :return: None
        """
        with open(self.get_filepath("report.md"), "a") as f:
            f.write("\n\nGenerated Files\n---------\n\n")
            f.write(
                f"[Branch 1 Output](https://raw.githubusercontent.com/{repo}/artifacts/{pr_number}/results/{branch1}.json)\n"
            )
            f.write(
                f"[Branch 2 Output](https://raw.githubusercontent.com/{repo}/artifacts/{pr_number}/results/{branch2}.json)\n"
            )
            f.write(
                f"[Full Output CSV ](https://raw.githubusercontent.com/{repo}/artifacts/{pr_number}/results/output.csv)\n"
            )

    def generate_time_chart(self, main, branch) -> None:
        """Generate time chart showing speed across branches

        return: None
        """

        with open(f"benchmark/{main}.json", "r") as f:
            main_file = json.load(f)
        with open(f"benchmark/{branch}.json", "r") as b:
            branch_file = json.load(b)

        with open("benchmark/output.csv", "w") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["ID", "Gain", "Loss"])

            for (m, b) in zip(main_file, branch_file):
                if set(m["cites"]) == set(b["cites"]):
                    continue

                changes = set(m["cites"]) ^ set(b["cites"])
                for change in list(changes):
                    gain, loss = "", ""
                    if change in m["cites"]:
                        loss = change
                    else:
                        gain = change
                    writer.writerow([m["id"], gain, loss])

        plt.plot(
            [x["time"] for x in main_file],
            [x["total"] for x in main_file],
            label=f"Main/{main}",
        )
        plt.plot(
            [x["time"] for x in branch_file],
            [x["total"] for x in branch_file],
            label=branch,
        )
        plt.legend(loc="upper left")
        plt.ylabel("# Cites Found ", rotation="vertical")
        plt.xlabel("Seconds")
        plt.title("Comparison of Branches")
        plt.savefig(self.get_filepath("chart.png"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pr")
    parser.add_argument("--branches", nargs="+")
    parser.add_argument("--reporters", action="store_true")

    args = parser.parse_args()
    repo = (
        "freelawproject/reporters-db" if args.reporters else "freelawproject/eyecite"
    )  # this will be updated to our branches
    benchmark = Benchmark()
    if len(args.branches) == 1:
        benchmark.generate_branch_report(branch=args.branches[0])
    elif len(args.branches) == 2:
        benchmark.generate_branch_report(branch=args.branches[1])
        benchmark.generate_time_chart(args.branches[0], args.branches[1])
        benchmark.write_report(repo=repo, pr_number=args.pr)
        benchmark.append_links(
            args.branches[0], args.branches[1], args.pr, repo
        )
