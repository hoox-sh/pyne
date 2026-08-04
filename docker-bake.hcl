# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Docker Buildx Bake definition for PYNE images.
#
# Usage:
#   docker buildx bake                  # default group: api + api-dev (load local)
#   docker buildx bake api              # production API only
#   docker buildx bake api-dev lsp      # named targets
#   docker buildx bake release          # multi-platform (set REGISTRY to push)
#
# Variables (override with --set or env via bake HCL):
#   TAG=0.3.0 REGISTRY=gcr.io/PROJECT/pynescript docker buildx bake release

variable "TAG" {
  default = "latest"
}

variable "REGISTRY" {
  # Empty → local image names only (docker.io-less short names)
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
  targets = ["api", "api-dev", "lsp"]
}

group "release" {
  targets = ["api-release"]
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

# Multi-platform production image. When REGISTRY is set, bake pushes;
# otherwise it builds to the local build cache (no single-arch docker load).
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
