/**
 * Copyright (c) 2026 HOOX · PYNE · hoox-sh
 * SPDX-License-Identifier: AGPL-3.0-or-later
 */

import { describe, expect, it } from "bun:test";
import { execFileSync, spawnSync } from "node:child_process";
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { compileBundle } from "../../scripts/okf/compile";
import { collectInputs } from "../../scripts/okf/io";

const SCRATCH = "scripts/okf_gitignored_scratch.py";
const TRACKED = "scripts/okf_tracked_keep.py";

function git(cwd: string, args: string[]): string {
    return execFileSync(
        "git",
        [
            "-c",
            "user.email=okf@example.com",
            "-c",
            "user.name=okf",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "core.hooksPath=/dev/null",
            ...args,
        ],
        { cwd, encoding: "utf8" },
    );
}

function bundleText(
    root: string,
    options: { fromIndex?: boolean; walk?: boolean },
): string {
    const files = collectInputs(root, options);
    const bundle = compileBundle({
        files,
        existing: new Map(),
        now: "2026-11-18T00:00:00Z",
    });
    return [...bundle.values()].join("\n");
}

const REPO = join(import.meta.dir, "../..");

describe("OKF enrich sources", () => {
    it("advertises --walk and refuses to mix it with --from-index", () => {
        const help = spawnSync(
            "bun",
            ["scripts/okf/cli.ts", "enrich", "--help"],
            { cwd: REPO, encoding: "utf8" },
        );
        expect(help.status).toBe(0);
        expect(help.stdout).toContain("--walk");
        expect(help.stdout).toContain("default: tracked files only");

        const mixed = spawnSync(
            "bun",
            ["scripts/okf/cli.ts", "enrich", "--walk", "--from-index"],
            { cwd: REPO, encoding: "utf8" },
        );
        expect(mixed.status).toBe(1);
        expect(mixed.stderr).toContain(
            "pass only one of --walk or --from-index",
        );
    });

    it("default matches --from-index and ignores a gitignored scratch file", () => {
        const root = mkdtempSync(join(tmpdir(), "okf-enrich-"));
        try {
            git(root, ["init", "-q"]);
            mkdirSync(join(root, "scripts"));
            writeFileSync(
                join(root, TRACKED),
                '"""Tracked keep file."""\n\ndef okf_tracked_keep():\n    return 1\n',
            );
            writeFileSync(
                join(root, ".gitignore"),
                "scripts/okf_gitignored_scratch.py\n",
            );
            git(root, ["add", "--", ".gitignore", TRACKED]);
            git(root, ["commit", "-q", "--no-verify", "-m", "init"]);
            writeFileSync(
                join(root, SCRATCH),
                '"""Gitignored scratch. Must not enter the default bundle."""\n\ndef okf_gitignored_scratch():\n    return 1\n',
            );
            expect(git(root, ["check-ignore", SCRATCH]).trim()).toBe(SCRATCH);

            const tracked = collectInputs(root)
                .map((file) => file.path)
                .sort();
            const fromIndex = collectInputs(root, { fromIndex: true })
                .map((file) => file.path)
                .sort();
            const walked = collectInputs(root, { walk: true })
                .map((file) => file.path)
                .sort();

            expect(tracked).toEqual(fromIndex);
            expect(tracked).toContain(TRACKED);
            expect(tracked).not.toContain(SCRATCH);
            expect(walked).toContain(SCRATCH);

            const byDefault = bundleText(root, {});
            const byWalk = bundleText(root, { walk: true });
            expect(byDefault).toContain("okf_tracked_keep.py");
            expect(byDefault).not.toContain("okf_gitignored_scratch.py");
            expect(byWalk).toContain("okf_gitignored_scratch.py");
            console.log(
                "okf enrich default ignored gitignored scratch; --walk included it",
            );
        } finally {
            rmSync(root, { recursive: true, force: true });
        }
    });
});
