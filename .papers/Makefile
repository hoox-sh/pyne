# Build all PYNE arXiv papers
# Prefer tectonic (auto package fetch); fall back to pdflatex + bibtex.
PAPERS := paper01-architecture paper02-compiler paper03-series-runtime \
          paper04-grammar paper05-parity-strategy paper06-lsp-tooling

.PHONY: all clean distclean draft check tectonic pdflatex $(PAPERS)

all: tectonic

tectonic:
	@command -v tectonic >/dev/null || { echo "tectonic not found; try: make pdflatex"; exit 1; }
	@for p in $(PAPERS); do \
	  echo "=== tectonic $$p ==="; \
	  (cd $$p && tectonic main.tex) || exit 1; \
	  echo "=== $$p/main.pdf ==="; \
	done

pdflatex: $(PAPERS)

$(PAPERS):
	@echo "=== Building $@ (pdflatex) ==="
	cd $@ && \
	  pdflatex -interaction=nonstopmode main.tex && \
	  bibtex main && \
	  pdflatex -interaction=nonstopmode main.tex && \
	  pdflatex -interaction=nonstopmode main.tex
	@echo "=== $@ done: $@/main.pdf ==="

draft:
	@for p in $(PAPERS); do \
	  echo "Draft $$p"; \
	  if command -v tectonic >/dev/null; then (cd $$p && tectonic main.tex) || true; \
	  else (cd $$p && pdflatex -interaction=nonstopmode main.tex) || true; fi; \
	done

clean:
	@for p in $(PAPERS); do \
	  rm -f $$p/*.aux $$p/*.bbl $$p/*.blg $$p/*.log $$p/*.out $$p/*.toc \
	        $$p/*.lof $$p/*.lot $$p/*.fls $$p/*.fdb_latexmk $$p/*.synctex.gz \
	        $$p/*.xdv $$p/*.bcf $$p/*.run.xml; \
	done

distclean: clean
	@for p in $(PAPERS); do rm -f $$p/main.pdf; done

check:
	@for p in $(PAPERS); do \
	  test -f $$p/main.tex || { echo "missing $$p/main.tex"; exit 1; }; \
	  echo "OK $$p/main.tex ($$(wc -l < $$p/main.tex) lines)"; \
	done
	@echo "All paper sources present."
