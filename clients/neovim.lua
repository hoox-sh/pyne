-- ~/.config/nvim/lua/lsp/pynescript.lua
-- Pine Script LSP configuration for Neovim
-- Usage: Add to your init.lua or use with nvim-lspconfig
--
-- With nvim-lspconfig:
--   require('lspconfig').pynescript.setup({})
--
-- Manual setup (no nvim-lspconfig needed):
--   require('lspconfig').pynescript.setup {
--     cmd = { 'pyne-lsp' },  -- alias: pynescript-lsp
--     filetypes = { 'pinescript' },
--     root_dir = function(fname)
--       return vim.fs.root(fname, { '.git', '*.pine', '*.pinev5', '*.pinev6' })
--         or vim.fn.getcwd()
--     end,
--     settings = {
--       pinescript = {
--         formatting = { enabled = true },
--         diagnostics = { enabled = true },
--       },
--     },
--     on_attach = function(client, bufnr)
--       -- Optional: set up keybindings
--       vim.keymap.set('n', 'gd', vim.lsp.buf.definition, { buffer = bufnr })
--       vim.keymap.set('n', 'gr', vim.lsp.buf.references, { buffer = bufnr })
--       vim.keymap.set('n', 'K', vim.lsp.buf.hover, { buffer = bufnr })
--     end,
--   }

return {
  cmd = { 'pyne-lsp' },  -- or 'pynescript-lsp'
  filetypes = { 'pinescript' },
  root_dir = function(fname)
    return vim.fs.root(fname, { '.git', '*.pine', '*.pinev5', '*.pinev6', 'pyproject.toml' })
      or vim.fn.getcwd()
  end,
  settings = {
    pinescript = {
      formatting = { enabled = true },
      diagnostics = { enabled = true },
      completion = { snippets = true },
    },
  },
  handlers = {
    ['window/showMessage'] = function(_, params)
      vim.notify(params.message, vim.log.levels.INFO, { title = 'Pine Script' })
    end,
  },
}
