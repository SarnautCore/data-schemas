# m2-quest-unsupported

One quest whose only objective is `quest-count-special`, the third kind
`mechanics/quests.md` rule 5.5 names and the one M2 does not implement.

The layer exists so that "the shard refuses a pack it cannot play, loudly, and
names the quest" is a claim a test can make against a real compiled pack rather
than against a hand-built struct. Rule 5.5.6 puts that refusal at content-load
and not at completion time, because a `quest-count-special` objective is driven
by the impact system: a shard that loaded it anyway would offer a player a
quest that can never be completed and would find out only when somebody
complained.

`sarnaut-pack` compiles the objective rather than dropping it — ten of the M2
zone's twelve objectives are this kind, and a compiler that silently discarded
them would hand the shard exactly the quest it is supposed to refuse.

The layer is not applied by default. Building it produces a pack that loads
(the bytes are well formed) and that `internal/quests` then refuses:

```powershell
cargo run -p sarnaut-pack -- build --fixture `
  --src ..\data-schemas\demo `
  --overlay m2-quest-unsupported `
  --out ..\server\testdata\packs\demo-quest-unsupported
```
