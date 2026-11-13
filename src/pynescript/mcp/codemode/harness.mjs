/**
 * Copyright (C) 2024-2026 jango_blockchained
 * SPDX-License-Identifier: AGPL-3.0-or-later
 *
 * Code Mode sandbox harness.
 *
 * This file runs INSIDE the boundary (see sandbox.py). It is never imported by
 * the server and it imports only Node built-ins: inside the boundary only this
 * file, the JavaScript runtime, and its shared libraries are readable.
 *
 * Trust model, in order of importance:
 *
 * 1. The boundary is the OS, not this file. The parent spawns this harness in a
 *    bwrap namespace with a cleared environment, no network, and no host
 *    filesystem. If every line below were wrong, the child still has no
 *    credentials, no repo, and nowhere to write.
 * 2. The parent is the policy enforcement point. This harness can ask for a
 *    `call`, but the parent re-resolves the tool, re-checks its risk class, and
 *    re-dispatches through the same path the direct tools use.
 * 3. The vm context below is capability shaping, not a security boundary. It
 *    removes `process`, `require`, and `fetch` so accidental escapes fail
 *    loudly instead of silently working.
 *
 * The one rule that keeps point 3 honest: nothing created in this file's realm
 * is handed to sandboxed code as an object. Only primitives cross in (strings),
 * and sandboxed code builds its own objects with JSON.parse inside the context.
 * A single host object would reopen the
 * `fn.constructor.constructor("return process")()` escape.
 */

import vm from "node:vm";
import process from "node:process";

const MAX_LOGS = 40;
const LOG_CHARS = 400;

const decoder = new TextDecoder();
let buffer = "";
let closed = false;
const replies = new Map();
let pendingJob = null;
let jobWaiter = null;

function send(message) {
  process.stdout.write(`${JSON.stringify(message)}\n`);
}

function dispatch(line) {
  let parsed;
  try {
    parsed = JSON.parse(line);
  } catch {
    return;
  }
  if (parsed.type === "reply") {
    const id = typeof parsed.id === "number" ? parsed.id : -1;
    const resolve = replies.get(id);
    if (resolve) {
      replies.delete(id);
      resolve(parsed);
    }
    return;
  }
  if (parsed.type === "job") {
    if (jobWaiter) {
      const wake = jobWaiter;
      jobWaiter = null;
      wake(parsed);
    } else {
      pendingJob = parsed;
    }
  }
}

async function readLoop() {
  for await (const chunk of process.stdin) {
    buffer += decoder.decode(chunk, { stream: true });
    let at = buffer.indexOf("\n");
    while (at >= 0) {
      const line = buffer.slice(0, at);
      buffer = buffer.slice(at + 1);
      if (line.length > 0) dispatch(line);
      at = buffer.indexOf("\n");
    }
  }
  closed = true;
  if (jobWaiter) {
    const wake = jobWaiter;
    jobWaiter = null;
    wake(null);
  }
}

function nextJob() {
  if (pendingJob) {
    const value = pendingJob;
    pendingJob = null;
    return Promise.resolve(value);
  }
  if (closed) return Promise.resolve(null);
  return new Promise((resolve) => {
    jobWaiter = resolve;
  });
}

let nextId = 1;

/**
 * Ask the parent to do something. Always resolves to a JSON string and never
 * rejects: a rejected promise would hand a host Error object to sandboxed code,
 * and `error.constructor` is a host Function.
 */
async function callHost(method, target, args) {
  const id = nextId;
  nextId += 1;
  const reply = new Promise((resolve) => {
    replies.set(id, resolve);
  });
  send({ type: "call", id, method, target, args });
  let message;
  try {
    message = await reply;
  } catch {
    return JSON.stringify({ __error: "host call failed" });
  }
  if (!message.ok) {
    return JSON.stringify({
      __error: typeof message.json === "string" ? message.json : "host call failed",
    });
  }
  return typeof message.json === "string" ? message.json : "null";
}

/**
 * Built inside the vm context. Every binding the model touches is created here,
 * so its `constructor` is the context's Function, and
 * `codeGeneration: { strings: false }` turns the classic escape into a throw.
 */
const CONTEXT_SOURCE = `(function (host, mode, catalogJson, namespacesJson, maxCalls) {
  "use strict";
  var calls = 0;
  var logs = [];
  var catalog = catalogJson === null ? null : JSON.parse(catalogJson);
  var namespaces = namespacesJson === null ? null : JSON.parse(namespacesJson);

  function fmt(value) {
    if (typeof value === "string") return value;
    try {
      var json = JSON.stringify(value);
      return json === undefined ? String(value) : json;
    } catch (err) {
      return String(value);
    }
  }

  function record(kind, args) {
    if (logs.length >= ${MAX_LOGS}) return;
    var parts = [];
    for (var i = 0; i < args.length; i += 1) parts.push(fmt(args[i]));
    logs.push((kind + ": " + parts.join(" ")).slice(0, ${LOG_CHARS}));
  }

  var consoleApi = {};
  var kinds = ["log", "info", "warn", "error", "debug", "trace"];
  for (var k = 0; k < kinds.length; k += 1) {
    (function (kind) {
      consoleApi[kind] = function () { record(kind, arguments); };
    })(kinds[k]);
  }

  async function call(method, target, args) {
    if (calls >= maxCalls) {
      throw new Error("sandbox call limit reached (" + maxCalls + ")");
    }
    calls += 1;
    var raw = await host.call(method, target, args);
    var reply = JSON.parse(raw);
    if (reply && reply.__error) throw new Error(String(reply.__error));
    return reply === null || reply === undefined ? null : reply.value;
  }

  var api = {};
  if (catalog !== null) api.catalog = catalog;
  if (mode === "execute") {
    api.call = function (target, args) { return call("call", target, args); };
    api.describe = function (target) { return call("describe", target, null); };
    if (namespaces !== null) {
      for (var group in namespaces) {
        if (!Object.prototype.hasOwnProperty.call(namespaces, group)) continue;
        (function (g) {
          var ns = {};
          var ops = namespaces[g];
          for (var op in ops) {
            if (!Object.prototype.hasOwnProperty.call(ops, op)) continue;
            (function (name, tool) {
              ns[name] = function (args) { return call("call", tool, args); };
            })(op, ops[op]);
          }
          api[g] = ns;
        })(group);
      }
    }
  }

  return { api: api, catalog: catalog, console: consoleApi, logs: logs, calls: function () { return calls; } };
})`;

async function run(job) {
  const context = vm.createContext(Object.create(null), {
    codeGeneration: { strings: false, wasm: false },
  });

  const build = vm.runInContext(CONTEXT_SOURCE, context);
  const built = build(
    { call: callHost },
    job.mode,
    job.catalog,
    job.namespaces,
    job.maxCalls
  );
  context.pyne = built.api;
  context.console = built.console;
  if (built.catalog !== null) context.catalog = built.catalog;

  const source = `(${job.code.trim().replace(/;+$/, "")}\n)`;
  let fn;
  try {
    fn = vm.runInContext(source, context);
  } catch (err) {
    send({
      type: "error",
      message: `code must be a JavaScript async arrow function: ${
        err instanceof Error ? err.message : String(err)
      }`,
    });
    return;
  }
  if (typeof fn !== "function") {
    send({ type: "error", message: "code did not evaluate to a function" });
    return;
  }

  let value;
  try {
    value = await fn();
  } catch (err) {
    send({
      type: "error",
      message: err instanceof Error ? err.message : String(err),
    });
    return;
  }

  let json;
  try {
    const encoded = JSON.stringify(value === undefined ? null : value);
    json = encoded === undefined ? "null" : encoded;
  } catch (err) {
    send({
      type: "error",
      message: `result is not JSON-serializable: ${
        err instanceof Error ? err.message : String(err)
      }`,
    });
    return;
  }

  send({
    type: "done",
    json,
    calls: built.calls(),
    logs: built.logs.slice(0, MAX_LOGS),
  });
}

async function main() {
  void readLoop();
  const job = await nextJob();
  if (!job) {
    send({ type: "error", message: "sandbox received no job" });
    return;
  }
  await run(job);
}

await main();
