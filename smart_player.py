from __future__ import annotations

from board import Entity, neighbors, toroidal_distance_2
import numpy as np
import numpy.typing as npt

AntMove = tuple[tuple[int, int], tuple[int, int]]


class SmartBot:
    def __init__(self, walls: npt.NDArray[np.int_], harvest_radius: int, vision_radius: int, battle_radius: int, max_turns: int, time_per_turn: float) -> None:
        self.walls = walls
        self.collect_radius = harvest_radius
        self.vision_radius = vision_radius
        self.battle_radius = battle_radius
        self.max_turns = max_turns
        self.time_per_turn = time_per_turn
        self.turn = 0
        self.shape = (int(walls.shape[0]), int(walls.shape[1]))
        self.battle_r2 = battle_radius * battle_radius

    @property
    def name(self) -> str:
        return "danielz_bot"

    def move_ants(self, vision: set[tuple[tuple[int, int], Entity]], stored_food: int,) -> set[AntMove]:
        self.turn += 1
        #jotting everything down
        my_ants = [coord for coord, kind in vision if kind == Entity.FRIENDLY_ANT]
        my_hills = {coord for coord, kind in vision if kind == Entity.FRIENDLY_HILL}
        enemy_ants = [coord for coord, kind in vision if kind == Entity.ENEMY_ANT]
        seen_enemy_hills = {coord for coord, kind in vision if kind == Entity.ENEMY_HILL}
        food = [coord for coord, kind in vision if kind == Entity.FOOD]

        if not my_ants:
            return set()
        #infer where enemy hills are
        inferred_hills = {self.mirror(h) for h in my_hills}
        hill_targets = list(seen_enemy_hills | inferred_hills)
        food_targets = food
        #this sort of limits ants from just getting food all the time
        #so it doesnt literally scan every food and time out
        #idk this is what worked
        if len(food) > 28:
            food_targets = sorted(food, key=lambda f: self.nearest(f, my_hills)[1])[:28]

        ants = sorted(my_ants, key=lambda a: (a not in my_hills, a[0], a[1]))
        enemy_ants_set = set(enemy_ants)

        claimed: set[tuple[int, int]] = set(my_hills)
        out: set[AntMove] = set()
        food_claims: dict[tuple[int, int], int] = {}
        #decided to just designate some ants as raiders which will literally just go get hills
        raider_count = 0
        if hill_targets and len(ants) >= 6: #only if more thna six
            raider_count = max(1, len(ants) // (4 if stored_food > len(my_hills) else 6))
        raiders = set()
        if raider_count: #looks to closest ants to a hill to be designated raiders
            raiders = {
                ant
                for ant, _ in sorted(
                    ((ant, self.nearest(ant, hill_targets)[1]) for ant in ants),
                    key=lambda x: x[1],
                )[:raider_count]
            }

        for ant in ants:
            #get all legal moves that arent claimed by other ants already or arent walls
            possible = [n for n in neighbors(ant, self.shape) if not self.walls[n] and n not in claimed]
            if not possible:
                claimed.add(ant)
                continue
            #get away from the hill allow the spawning of more ants
            if ant in my_hills:
                off_hill = [m for m in possible if m not in my_hills]
                if off_hill:
                    possible = off_hill

            nearest_enemy, enemy_d = self.nearest(ant, enemy_ants_set)

            if (nearest_enemy is not None and enemy_d <= (self.battle_radius + 2) ** 2 and ant not in raiders):
                # retreat code
                dest = max(
                    possible,
                    key=lambda m: (
                        self.di(m, nearest_enemy),
                        self.explore_score(m, my_hills),
                    ),
                )
            else:
                # find a target and go
                target: tuple[int, int] | None = None
                if ant in raiders and hill_targets:
                    #if a designated attacker go for a hill
                    target, _ = self.nearest(ant, hill_targets)
                if target is None and food_targets:
                    # if nothing to go for just gather food
                    target = min(
                        food_targets,
                        key=lambda f: self.di(ant, f) + 6 * food_claims.get(f, 0),
                    )
                if target is None and nearest_enemy is not None:
                    target = nearest_enemy
                if target is None and hill_targets:
                    target, _ = self.nearest(ant, hill_targets)

                if target is not None:
                    best_dist = min(self.di(m, target) for m in possible)
                    tied = [m for m in possible if self.di(m, target) == best_dist]
                    dest = max(
                        tied,
                        key=lambda m: (
                            self.di(m, nearest_enemy) if nearest_enemy is not None else float("inf"),
                            self.explore_score(m, my_hills),
                        ),
                    )
                    if target in food_claims or target in food:
                        food_claims[target] = food_claims.get(target, 0) + 1
                else:
                    dest = max(
                        possible,
                        key=lambda m: (
                            self.explore_score(m, my_hills),
                            self.di(m, nearest_enemy) if nearest_enemy is not None else float("inf"),
                        ),
                    )

            claimed.add(dest)
            out.add((ant, dest))

        return out

    def nearest(self, start: tuple[int, int],targets: list[tuple[int, int]] | set[tuple[int, int]],) -> tuple[tuple[int, int] | None, float]:
        nearest = None
        best = float("inf")
        for t in targets:
            d = self.di(start, t)
            if d < best:
                best = d
                nearest = t
        return nearest, best
    
    #friend of mine gave me an idea to make this sort of
    # fake random exploration, any ant in the tile will go the same route
    #bi

    def explore_score(self, loc: tuple[int, int], my_hills: set[tuple[int, int]]) -> float:
        hill_d2 = min((self.di(loc, h) for h in my_hills), default=0.0)
        random_motion = (loc[0] * 31 + loc[1] * 17 + self.turn * 13) % 23
        return hill_d2 + 0.1 * random_motion
    # to find enemy hills
    def mirror(self, loc: tuple[int, int]) -> tuple[int, int]:
        return (self.shape[0] - loc[0] - 1, self.shape[1] - loc[1] - 1)

    def di(self, a: tuple[int, int], b: tuple[int, int]) -> float:
        return toroidal_distance_2(a, b, self.shape)
