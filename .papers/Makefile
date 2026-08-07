# Build all PYNE arXiv papers
# Prefer tectonic (auto package fetch); fall back to pdflatex + bibtex.
PAPERS := paper01-architecture paper02-compiler paper03-series-runtime \
          paper04-grammar paper05-parity-strategy paper06-lsp-tooling
SERIES := series-complete

.PHONY: all clean distclean draft check tectonic pdflatex series $(PAPERS)

all: tectonic series

tectonic:
	@command -v tectonic >/dev/null || { echo "tectonic not found; try: make pdflatex"; exit 1; }
	@for p in $(PAPERS); do \
	  echo "=== tectonic $$p ==="; \
	  (cd $$p && tectonic main.tex) || exit 1; \
	  echo "=== $$p/main.pdf ==="; \
	done

# Single volume with every page of every paper (+ cover + TOC).
# Builds individual papers first if any main.pdf is missing.
series:
	@command -v tectonic >/dev/null || { echo "tectonic not found"; exit 1; }
	@for p in $(PAPERS); do \
	  if [ ! -f $$p/main.pdf ]; then \
	    echo "=== missing $$p/main.pdf; building papers ==="; \
	    $(MAKE) tectonic; \
	    break; \
	  fi; \
	done
	@echo "=== tectonic $(SERIES) (complete volume) ==="
	cd $(SERIES) && tectonic main.tex
	@echo "=== $(SERIES)/main.pdf ==="
	cp -f $(SERIES)/main.pdf PYNE-paper-series-complete.pdf
	@echo "=== PYNE-paper-series-complete.pdf ==="

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
	@for p in $(PAPERS) $(SERIES); do \
	  rm -f $$p/*.aux $$p/*.bbl $$p/*.blg $$p/*.log $$p/*.out $$p/*.toc \
	        $$p/*.lof $$p/*.lot $$p/*.fls $$p/*.fdb_latexmk $$p/*.synctex.gz \
	        $$p/*.xdv $$p/*.bcf $$p/*.run.xml; \
	done

distclean: clean
	@for p in $(PAPERS) $(SERIES); do rm -f $$p/main.pdf; done
	@rm -f PYNE-paper-series-complete.pdf

check:
	@for p in $(PAPERS); do \
	  test -f $$p/main.tex || { echo "missing $$p/main.tex"; exit 1; }; \
	  echo "OK $$p/main.tex ($$(wc -l < $$p/main.tex) lines)"; \
	done
	@test -f $(SERIES)/main.tex || { echo "missing $(SERIES)/main.tex"; exit 1; }
	@echo "OK $(SERIES)/main.tex (complete volume binder)"
	@echo "All paper sources present."
