.PHONY: help docker-build docker-run docker-stop ghcr-login ghcr-tag ghcr-push ghcr-push-all file-search-export

IMAGE_NAME ?= cocom
LOCAL_IMAGE ?= $(IMAGE_NAME)
LOCAL_TAG ?= latest
LOCAL_REF ?= $(LOCAL_IMAGE):$(LOCAL_TAG)

CONTAINER_NAME ?= $(IMAGE_NAME)
HOST_PORT ?= 8000
CONTAINER_PORT ?= 8000

GHCR_REGISTRY ?= ghcr.io
GHCR_NAMESPACE ?= your-org-or-user
GHCR_IMAGE ?= $(GHCR_REGISTRY)/$(GHCR_NAMESPACE)/$(IMAGE_NAME)
GHCR_TAG ?= latest
GHCR_EXTRA_TAG ?= $(shell git rev-parse --short HEAD 2>/dev/null || echo dev)

help:
	@echo "Targets:"
	@echo "  make docker-build"
	@echo "  make docker-run"
	@echo "  make docker-stop"
	@echo "  make file-search-export"
	@echo "  make ghcr-tag GHCR_NAMESPACE=<owner>"
	@echo "  make ghcr-push GHCR_NAMESPACE=<owner> GHCR_TAG=<tag>"
	@echo "  make ghcr-push-all GHCR_NAMESPACE=<owner> GHCR_TAG=<tag> GHCR_EXTRA_TAG=<tag>"
	@echo ""
	@echo "Variables:"
	@echo "  IMAGE_NAME=$(IMAGE_NAME)"
	@echo "  LOCAL_IMAGE=$(LOCAL_IMAGE)"
	@echo "  LOCAL_TAG=$(LOCAL_TAG)"
	@echo "  CONTAINER_NAME=$(CONTAINER_NAME)"
	@echo "  HOST_PORT=$(HOST_PORT)"
	@echo "  CONTAINER_PORT=$(CONTAINER_PORT)"
	@echo "  GHCR_REGISTRY=$(GHCR_REGISTRY)"
	@echo "  GHCR_NAMESPACE=$(GHCR_NAMESPACE)"
	@echo "  GHCR_IMAGE=$(GHCR_IMAGE)"
	@echo "  GHCR_TAG=$(GHCR_TAG)"
	@echo "  GHCR_EXTRA_TAG=$(GHCR_EXTRA_TAG)"

docker-build:
	docker build -t $(LOCAL_REF) .

docker-run:
	docker run --rm -it -p $(HOST_PORT):$(CONTAINER_PORT) --name $(CONTAINER_NAME) $(LOCAL_REF)

docker-stop:
	docker stop $(CONTAINER_NAME)

file-search-export:
	uv run export-file-search

ghcr-login:
	@echo "Login example:"
	@echo "  echo \$\$GITHUB_TOKEN | docker login $(GHCR_REGISTRY) -u <github-user> --password-stdin"

ghcr-tag: docker-build
	docker tag $(LOCAL_REF) $(GHCR_IMAGE):$(GHCR_TAG)
	docker tag $(LOCAL_REF) $(GHCR_IMAGE):$(GHCR_EXTRA_TAG)

ghcr-push: docker-build
	docker tag $(LOCAL_REF) $(GHCR_IMAGE):$(GHCR_TAG)
	docker push $(GHCR_IMAGE):$(GHCR_TAG)

ghcr-push-all: ghcr-tag
	docker push $(GHCR_IMAGE):$(GHCR_TAG)
	docker push $(GHCR_IMAGE):$(GHCR_EXTRA_TAG)
