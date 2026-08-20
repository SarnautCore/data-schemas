# Overlay: m2-combat-extended

A second ability and a second mob, layered over `demo/` with
`sarnaut-pack build --overlay`.

It exists to be an exhibit, not a feature. `mechanics/combat.md` says every
combat rule is content, so the server suite compiles this overlay into a
second pack and runs the same combat assertions over it with no Go source
change. Nothing here overrides a base document; an overlay adds, and a
duplicate id is a build error.

The numbers are chosen to differ from the base dataset in every dimension the
shard reads: range, per-ability cooldown, damage coefficient, mob level,
`hp_mod`, aggro radius, leash radius and respawn window. A reader that pinned
one of them to a constant fails here.
