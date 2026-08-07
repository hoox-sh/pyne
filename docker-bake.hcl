# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Docker Buildx Bake definition for PYNE images.
#
# Usage:
#   docker buildx bake                  # default group: api + api-dev (load local)
#   docker buildx bake api              # production API only
#   docker buildx bake cli              # pynescript Click CLI
#   docker buildx bake api-dev lsp cli  # named targets
#   docker buildx bake release          # multi-platform (set REGISTRY to push)
#
# Variables (override with --set or env via bake HCL):
#   TAG=0.3.0 REGISTRY=gcr.io/PROJECT/pynescript docker buildx bake release
#
# Push safety: release targets use output type=registry ONLY when REGISTRY is
# non-empty. Empty REGISTRY keeps type=image (build cache / multi-arch manifest
# in the builder — never pushes to docker.io by accident).

variable "TAG" {
  default = "latest"
}

variable "REGISTRY" {
  # Empty → local short names only (no registry host, no push)
  default = ""
}

variable "PYNESCRIPT_VERSION" {
  default = "0.3.0"
}

variable "GIT_SHA" {
  default = "unknown"
}

variable "PYTHON_VERSION" {
  default = "3.12"
}

variable "PLATFORMS" {
  # release group only; local builds use the host platform
  default = "linux/amd64,linux/arm64"
}

function "image_name" {
  params = [name]
  result = REGISTRY != "" ? "${REGISTRY}/${name}" : name
}

group "default" {
  targets = ["api", "api-dev"]
}

group "all" {
  targets = ["api", "api-dev", "lsp", "cli"]
}

group "release" {
  targets = ["api-release", "cli-release"]
}

target "_common" {
  context    = "."
  dockerfile = "Dockerfile"
  args = {
    PYTHON_VERSION     = PYTHON_VERSION
    PYNESCRIPT_VERSION = PYNESCRIPT_VERSION
    GIT_SHA            = GIT_SHA
  }
  # Local BuildKit pip cache is declared in the Dockerfile via RUN --mount
}

target "api" {
  inherits = ["_common"]
  target   = "api"
  tags = [
    "${image_name("pynescript-api")}:${TAG}",
    "${image_name("pynescript-api")}:latest",
  ]
  output = ["type=docker"]
}

target "api-dev" {
  inherits = ["_common"]
  target   = "api-dev"
  tags = [
    "${image_name("pynescript-api")}:dev",
  ]
  output = ["type=docker"]
}

target "lsp" {
  inherits = ["_common"]
  target   = "lsp"
  tags = [
    "${image_name("pynescript-lsp")}:${TAG}",
    "${image_name("pynescript-lsp")}:latest",
  ]
  output = ["type=docker"]
}

target "cli" {
  inherits = ["_common"]
  target   = "cli"
  tags = [
    "${image_name("pynescript-cli")}:${TAG}",
    "${image_name("pynescript-cli")}:latest",
  ]
  output = ["type=docker"]
}

# Multi-platform production images.
# REGISTRY set  → push (type=registry)
# REGISTRY empty → type=image only (no push; no docker load for multi-arch)
target "api-release" {
  inherits   = ["_common"]
  target     = "api"
  platforms  = split(",", PLATFORMS)
  tags = [
    "${image_name("pynescript-api")}:${TAG}",
    "${image_name("pynescript-api")}:latest",
  ]
  output = REGISTRY != "" ? ["type=registry"] : ["type=image"]
  cache-from = [
    "type=local,src=/tmp/.buildx-cache-pynescript",
  ]
  cache-to = [
    "type=local,dest=/tmp/.buildx-cache-pynescript,mode=max",
  ]
}

target "cli-release" {
  inherits   = ["_common"]
  target     = "cli"
  platforms  = split(",", PLATFORMS)
  tags = [
    "${image_name("pynescript-cli")}:${TAG}",
    "${image_name("pynescript-cli")}:latest",
  ]
  output = REGISTRY != "" ? ["type=registry"] : ["type=image"]
  cache-from = [
    "type=local,src=/tmp/.buildx-cache-pynescript-cli",
  ]
  cache-to = [
    "type=local,dest=/tmp/.buildx-cache-pynescript-cli,mode=max",
  ]
}
