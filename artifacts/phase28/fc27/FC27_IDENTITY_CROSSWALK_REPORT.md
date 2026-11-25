# FC27 identity crosswalk

Four archives supplied three distinct CSV tables. The 19,789-row player snapshots were equal after normalizing their published date formats. The existing non-commercial player snapshot is the only one used for V3.2.

October provides 10,762 observations with 9,907 distinct base IDs. The card-item file provides 9,962 unique item IDs. There are 7,698 matching item IDs with the same overall rating, and 14 rating conflicts when a card item ID is compared directly to a player ID. Those are separate joins across distinct namespaces. Source observations preserve original keys, row numbers, rarity and raw values.

A provisional base association requires an October item match, a base ID in the player snapshot, an agreeing item rating and a matching normalized name. These signals yield 519 provisional candidates, 9,021 ambiguous, 408 unmatched and 14 conflicted observations. No association is automatically resolved. Card rarity is retained on the item. Ambiguous position codes and source-specific editorial role strings are retained with their original evidence.

The generated conflict CSV is local research evidence. The release archive carries aggregate counts and the script that reproduces that queue from the owner-supplied files.
