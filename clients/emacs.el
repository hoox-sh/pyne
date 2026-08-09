;; Pine Script LSP configuration for Emacs
;; Add to ~/.emacs.d/init.el or ~/.emacs.d/lisp/pynescript.el

;; Option 1: With use-package and lsp-mode (recommended)
(use-package lsp-mode
  :ensure t
  :hook ((pinescript-mode . lsp))
  :config
  (lsp-register-client
   (make-lsp-client
    :new-connection (lsp-stdio-connection '("pyne-lsp" "--stdio"))
    :major-modes '(pinescript-mode)
    :server-id 'pynescript
    :activation-fn (lsp-activate-on "pinescript" "*.pine" "*.pinev5" "*.pinev6"))))

;; Option 2: With straight.el
;; (use-package lsp-mode :straight t)

;; Define pinescript-mode if not already defined
(define-derived-mode pinescript-mode prog-mode "Pine Script"
  "Major mode for Pine Script."
  :syntax-table (standard-syntax-table)
  (setq font-lock-defaults '(pinescript-font-lock-keywords))
  (setq comment-start "//")
  (setq comment-end ""))

;; Optional: Font locking
(defvar pinescript-font-lock-keywords
  '(("\\(?:if\\|else\\|for\\|while\\|switch\\|return\\|break\\|continue\\)\\b" . font-lock-keyword-face)
    ("\\(?:import\\|from\\|as\\|type\\|method\\|var\\|const\\|strategy\\|indicator\\|library\\)\\b" . font-lock-keyword-face)
    ("\\(?:and\\|or\\|not\\|in\\|to\\)\\b" . font-lock-operator-face)
    ("\\(?:true\\|false\\|na\\|na\\)\\b" . font-lock-constant-face)
    ("\\(?:ta\\.[a-z_]+\\|strategy\\.[a-z_]+\\|array\\.[a-z_]+\\|matrix\\.[a-z_]+\\|math\\.[a-z_]+\\|str\\.[a-z_]+\\)" . font-lock-builtin-face)
    ("//.*$" . font-lock-comment-face)
    ("\"[^\"]*\"" . font-lock-string-face)))

;; Optional: Add to auto-mode-alist
(add-to-list 'auto-mode-alist '("\\.pine\\'" . pinescript-mode))
(add-to-list 'auto-mode-alist '("\\.pinev[0-9]+\\'" . pinescript-mode))

;; Optional: Key bindings
(add-hook 'pinescript-mode-hook
  (lambda ()
    (local-set-key (kbd "C-c C-c") 'lsp-document-format)
    (local-set-key (kbd "M-.") 'lsp-goto-definition)
    (local-set-key (kbd "M-?") 'lsp-find-references)))
