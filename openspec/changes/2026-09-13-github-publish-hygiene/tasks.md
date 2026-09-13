# Tasks: GitHub publish hygiene

## Implementation

- [x] Расширить `.gitignore` (creds, keys, `.mcp.json`, kubeconfig)
- [x] Добавить `registry.selectel.example` и `ingress_host.example`
- [x] Обновить каноническую `openspec/specs/webquik-mcp/spec.md`
- [x] Удалить закрытые дневные change-папки

## Verification

- [x] `registry.selectel`, `ingress_host`, `.mcp.json` игнорируются gitignore
- [x] Example-файлы не игнорируются
- [x] В канонической spec нет требования хранить брокерский пароль в Secret
