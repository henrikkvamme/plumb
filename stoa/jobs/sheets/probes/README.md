# Probes on large sheets (14 November)

Scripts from two experiments. They are not part of the agent. Each takes a scratch directory as its first argument
and has paths of that session in it: adjust them before a run.

## `door_compare.py`: door counts

It runs both detectors (`yolo26m`, `yolo26m-styles`) on a sheet, reads the door leaves (swing arcs) from the vector
PDF, and writes contact sheets of each disagreement.

| UK DfE sheet | leaves in PDF | yolo26m | yolo26m-styles | boxes of both |
| --- | --- | --- | --- | --- |
| special 00 | 127 | 129 | 125 | 124 |
| special 01 | 42 | 44 | 47 | 43 |
| primary 00 | 112 | 107 | 102 | 100 |
| primary 01 | 38 | 43 | 42 | 40 |
| secondary 00 | 196 | 200 | 203 | 177 |
| secondary 01 | 101 | 110 | 110 | 100 |
| secondary 02 | 32 | 51 | 54 | 47 |

- Special 00, checked by eye: 127 doors. `yolo26m` counts 4 chairs as doors and misses 2 doors. `yolo26m-styles`
  has no false door and misses 1 (on that run 126 boxes).
- The swing arcs are not a key: 22 real doors have no arc (store doors drawn as a slanted line, folding doors), and
  4 "leaves" are tables.
- The two detectors agree on the count on 1 sheet of 7, and there 18 boxes differ. An exact door count on a sheet
  with 40 to 200 doors is not safe. The agent abstains.

## `room_fill.py`: room areas

Walls are the dark strokes thicker than 8 cm. Each door and window box of the detector closes the wall gap near it.
A flood fill from the centre of a room label gives the room.

- On special 00 all 8 classrooms close, at 47 to 50 m2. Two variants of the seal differ by 0.2 to 0.6 m2 on them.
- Other rooms move more between variants: kitchen 42.5 to 48.9 m2, hall 234 to 242 m2, group rooms 4.0 to 5.6 m2.
- A door in a wall recess with a side panel needs a reach of 0.9 m around its box. That reach also fills parts of
  rooms narrower than about 1.6 m.
- There is no key. The next step is a key from the wall polygons of the vector PDF. Without it the tool is not in
  the agent.
- The dormitory concept plans do not work with this method: their inner walls are as thin as the leader lines.
