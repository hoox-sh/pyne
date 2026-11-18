/**
 * Copyright (c) 2026 HOOX · PYNE · hoox-sh
 * SPDX-License-Identifier: AGPL-3.0-or-later
 */

import { describe, expect, it } from "bun:test";
import { execFileSync, spawnSync } from "node:child_process";
import {
    cpSync,
    mkdtempSync,
    mkdirSync,
    readFileSync,
    rmSync,
    writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const REPO = join(import.meta.dir, "../..");

const PROBE = `"""Probe module for the OKF freshness gate."""

def okf_probe():
    return 1
`;

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

function okfCmd(): string {
    const text = readFileSync(join(REPO, "scripts/verify.sh"), "utf8");
    const match = text.match(/^OKF_CMD='([^']*)'/m);
    if (!match?.[1]) throw new Error("OKF_CMD missing from scripts/verify.sh");
    return match[1];
}

/** Tiny repo whose verify.sh is this worktree's script, not a stub. */
function fixture(): string {
    const root = mkdtempSync(join(tmpdir(), "okf-verify-"));
    git(root, ["init", "-q"]);
    mkdirSync(join(root, "scripts"));
    cpSync(join(REPO, "scripts/okf"), join(root, "scripts/okf"), {
        recursive: true,
    });
    cpSync(join(REPO, "scripts/verify.sh"), join(root, "scripts/verify.sh"));
    writeFileSync(join(root, "scripts/probe.py"), PROBE);
    git(root, ["add", "--", "scripts"]);
    git(root, ["commit", "-q", "--no-verify", "-m", "init"]);
    const enrich = spawnSync("bun", ["scripts/okf/cli.ts", "enrich"], {
        cwd: root,
        encoding: "utf8",
    });
    if (enrich.status !== 0) {
        throw new Error(
            `enrich failed (${enrich.status}): ${enrich.stdout}\n${enrich.stderr}`,
        );
    }
    git(root, ["add", "--", "okf"]);
    git(root, ["commit", "-q", "--no-verify", "-m", "bundle"]);
    return root;
}

function verify(root: string) {
    return spawnSync("bash", ["scripts/verify.sh", "pre-commit"], {
        cwd: root,
        encoding: "utf8",
        env: {
            ...process.env,
            OO_SKIP: "format,lint,typecheck",
            NO_COLOR: "1",
            TERM: "dumb",
        },
    });
}

describe("verify.sh OKF step", () => {
    it("keeps structure validation and checks freshness without walking", () => {
        const cmd = okfCmd();
        expect(cmd).toContain("okn --no-telemetry validate --spec 0.2 okf");
        expect(cmd).toContain("bun scripts/okf/cli.ts enrich --check");
        expect(cmd).not.toContain("--walk");
        const text = readFileSync(join(REPO, "scripts/verify.sh"), "utf8");
        expect(text).toContain('run_step okf "OKF" "$OKF_CMD"');
    });

    it("fails when the bundle is stale and passes when it matches", () => {
        const root = fixture();
        const probe = join(root, "scripts/probe.py");
        try {
            const fresh = verify(root);
            expect(fresh.status, `${fresh.stdout}\n${fresh.stderr}`).toBe(0);

            writeFileSync(
                probe,
                `${PROBE}\ndef okf_probe_stale():\n    return 2\n`,
            );
            const stale = verify(root);
            const staleOut = `${stale.stdout}\n${stale.stderr}`;
            expect(stale.status, staleOut).not.toBe(0);
            expect(staleOut).toContain("stale");

            writeFileSync(probe, PROBE);
            const again = verify(root);
            expect(again.status, `${again.stdout}\n${again.stderr}`).toBe(0);
        } finally {
            rmSync(root, { recursive: true, force: true });
        }
    });
});
