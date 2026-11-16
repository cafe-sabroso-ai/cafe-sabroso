"""Independent dinosaur wave factory over the shared arcade mechanics, not a zombie-room alias."""
from zombi_engine import (DINO_SCENES as SCENES,DINO_TYPES as TYPES,DINO_BOSSES as BOSSES,WEAPONS,DIRECTIONS,quota,alive,start_wave,fill_targets,choose_weapon,lose_life,finish_if_dead,next_turn,wave_reward,attack,expire_wave,continue_wave,buy,bot_target,clues,boss_total)
from zombi_engine import new_game as _shared_new_game

def new_game(seats,seed=None):return _shared_new_game(seats,seed,mode='dinosaurios')
