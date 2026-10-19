# Charmtone

The Charm™ color system.

<p>
  <img width="400" alt="CharmTone Banner" src="https://github.com/user-attachments/assets/c4ea8c9b-8bfc-4275-9aae-a059f458f535" /><br>
  <a href="https://github.com/charmbracelet/tone/releases"><img src="https://img.shields.io/github/release/charmbracelet/tone.svg" alt="Latest Release"></a>
  <a href="https://pkg.go.dev/charm.land/tone?tab=doc"><img src="https://godoc.org/charm.land/tone?status.svg" alt="GoDoc"></a>
  <a href="https://github.com/charmbracelet/tone/actions"><img src="https://github.com/charmbracelet/tone/actions/workflows/build.yml/badge.svg?branch=main" alt="Build Status"></a>
</p>

Charmtone is the Charm color system.

## Library

```bash
go get charm.land/tone
```

Every color is a `tone.Key`, which satisfies `color.Color`, so you can hand it
straight to [Lip Gloss](https://github.com/charmbracelet/lipgloss) or anything else that takes a color.

```go
import (
	"fmt"

	"charm.land/lipgloss/v2"
	"charm.land/tone"
)

style := lipgloss.NewStyle().
	Foreground(tone.Sash).
	Background(tone.Charple)

fmt.Println(tone.Charple, tone.Charple.Hex()) // Charple #6B50FF

for _, k := range tone.Spectrum() {
	fmt.Println(k, k.Hex())
}
```

See the [docs](https://pkg.go.dev/charm.land/tone) for the full API.

## CLI

```bash
# Homebrew
brew install charmbracelet/tap/charmtone
```

Packages for Arch (AUR), Debian, Fedora, Alpine, Nix, Scoop and Winget, plus
prebuilt binaries, are on the [releases][releases] page.

```bash
charmtone        # render the palette in your terminal
charmtone css    # CSS custom properties
charmtone scss   # SCSS variables
charmtone vim    # Vim variables
```

[releases]: https://github.com/charmbracelet/tone/releases

## License

[Apache 2.0](LICENSE). See [NOTICE](NOTICE).

## Whatcha think?

We’d love to hear your thoughts on this project. Need help? We gotchu. You can
find us on:

- [Twitter][twitter]
- [Discord][discord]
- [Slack][slack]
- [Bluesky][bsky]
- [The Fediverse][mastodon]

[twitter]: https://twitter.com/charmcli
[slack]: https://charm.land/slack
[discord]: https://charm.land/discord
[bsky]: https://bsky.app/profile/charm.land
[mastodon]: https://mastodon.social/@charmcli

---

Part of [Charm](https://charm.land).

<a href="https://charm.land/"><img alt="The Charm logo" width="400" src="https://stuff.charm.sh/charm-banner-softy.jpg" /></a>

Charm热爱开源 • Charm loves open source
