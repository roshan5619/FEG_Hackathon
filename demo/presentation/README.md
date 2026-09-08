# Presentation material

> ⚠️ **The pitch deck in the working folder is from an earlier, abandoned
> direction** (`MindTheGap_Pitch_Deck.pptx` — a sportsbook session-intelligence
> concept). It does **not** describe this submission and should not be
> submitted as-is.

## The deck to present

**Slide content: [`slides.md`](slides.md)** — every slide's headline, copy and
figures, ready to rebuild as `.pptx`. A presentable HTML version of the same
deck also exists; ask the team lead for the link.

## Why

The current solution is a **personalised casino lobby**: a game recommendation
system that replaces a static, identical-for-everyone lobby with rows driven by
each player's history.

If you rebuild the deck, these are the slides that matter:

1. **Problem** — the lobby is static; 26,904 players see the same
   *Najigranije* row; the most common route to a game is search
2. **Solution** — five rows, each justified by a measured result
3. **The honest finding** — collaborative filtering *lost* to most-played on
   next-game prediction (0.056 vs 0.305), so we kept the popularity row
4. **The result that justifies the build** — on the tail, where 76.5% of
   discovery happens, the trained ranker wins **4.28×** while reaching **732
   games against 29**
5. **Responsible play** — hard gates run before scoring; a self-excluded
   account is never scored, not filtered
6. **Architecture** — additive middleware on FEG's stack (Vue / Python / Redis)
7. **Impact & ask** — 680 reachable games vs 37; and the one ask that multiplies
   it: a game catalogue, since 83% of stake is on games we cannot name

Numbers and method: [`docs/evaluation.md`](../../docs/evaluation.md).
Run of show: [`demo-video-link.md`](../demo-video-link.md).
