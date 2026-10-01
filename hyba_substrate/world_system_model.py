"""Bounded coupled world-system scenario model.

This is a research seed, not a civilization-scale oracle.  All dimensions are
normalized, interventions are explicit, uncertainty is propagated, and no
forecast can directly trigger production actions.
"""
from __future__ import annotations
import math,time
from dataclasses import dataclass,field
from typing import Mapping
import numpy as np

DIMENSIONS=("economy","geopolitics","ecosystem","markets","human_behavior","technology")

def _unit_map(values:Mapping[str,float],name:str)->dict[str,float]:
    if set(values)!=set(DIMENSIONS):raise ValueError(f"{name} must contain exactly {DIMENSIONS}")
    result={k:float(values[k]) for k in DIMENSIONS}
    if any(not math.isfinite(v) or not 0<=v<=1 for v in result.values()):raise ValueError(f"{name} values must be finite and in [0,1]")
    return result

@dataclass(frozen=True)
class WorldState:
    values:dict[str,float];uncertainty:dict[str,float];step:int=0;timestamp:float=field(default_factory=time.time)
    def __post_init__(self):_unit_map(self.values,"values");_unit_map(self.uncertainty,"uncertainty")

@dataclass(frozen=True)
class WorldForecast:
    states:tuple[WorldState,...];scenario_name:str;interventions:dict[int,dict[str,float]]

@dataclass(frozen=True)
class CalibrationResult:
    mean_absolute_error:float;root_mean_squared_error:float;calibration_score:float

class WorldSystemModel:
    def __init__(self,coupling_matrix:np.ndarray|None=None,damping:float=.2,uncertainty_growth:float=.02):
        if not 0<damping<=1 or not 0<=uncertainty_growth<=1:raise ValueError("invalid damping or uncertainty growth")
        if coupling_matrix is None:
            coupling_matrix=np.array([[.35,-.10,-.08,.25,.08,.18],[-.12,.30,-.16,-.08,.18,.05],
             [-.10,-.08,.40,-.06,.12,.16],[.22,-.10,-.08,.32,.12,.20],[.10,.16,.12,.10,.35,.18],[.18,.05,.14,.20,.16,.40]],float)
        matrix=np.asarray(coupling_matrix,float)
        if matrix.shape!=(len(DIMENSIONS),len(DIMENSIONS)) or not np.all(np.isfinite(matrix)):raise ValueError("coupling matrix must be finite 6x6")
        spectral=max(abs(np.linalg.eigvals(matrix)))
        if spectral>1:raise ValueError("coupling matrix must have spectral radius <= 1")
        self.matrix=matrix;self.damping=float(damping);self.uncertainty_growth=float(uncertainty_growth);self._calibration=[]
    def forecast(self,initial:WorldState,steps:int,*,scenario_name:str="baseline",drivers:Mapping[str,float]|None=None,
                 interventions:Mapping[int,Mapping[str,float]]|None=None)->WorldForecast:
        if steps<=0:raise ValueError("steps must be positive")
        driver={k:0.0 for k in DIMENSIONS}
        for k,v in dict(drivers or {}).items():
            if k not in driver or not math.isfinite(float(v)) or abs(float(v))>1:raise ValueError("invalid driver")
            driver[k]=float(v)
        iv={int(step):dict(changes) for step,changes in dict(interventions or {}).items()}
        for step,changes in iv.items():
            if step<1 or step>steps:raise ValueError("intervention step out of range")
            for k,v in changes.items():
                if k not in DIMENSIONS or not math.isfinite(float(v)) or abs(float(v))>1:raise ValueError("invalid intervention")
        states=[initial];x=np.array([initial.values[k] for k in DIMENSIONS],float);u=np.array([initial.uncertainty[k] for k in DIMENSIONS],float)
        d=np.array([driver[k] for k in DIMENSIONS],float)
        for step in range(1,steps+1):
            centered=x-.5;target=np.clip(.5+self.matrix@centered+d,0,1);x=np.clip((1-self.damping)*x+self.damping*target,0,1)
            if step in iv:
                for k,v in iv[step].items():x[DIMENSIONS.index(k)]=np.clip(x[DIMENSIONS.index(k)]+float(v),0,1)
            interaction_uncertainty=np.abs(self.matrix)@u/len(DIMENSIONS);u=np.clip(u+self.uncertainty_growth+interaction_uncertainty*self.damping,0,1)
            states.append(WorldState(dict(zip(DIMENSIONS,map(float,x))),dict(zip(DIMENSIONS,map(float,u))),step))
        return WorldForecast(tuple(states),scenario_name,iv)
    def calibrate(self,forecast_state:WorldState,actual_values:Mapping[str,float])->CalibrationResult:
        actual=_unit_map(actual_values,"actual_values");pred=np.array([forecast_state.values[k] for k in DIMENSIONS]);truth=np.array([actual[k] for k in DIMENSIONS])
        mae=float(np.mean(abs(pred-truth)));rmse=float(np.sqrt(np.mean((pred-truth)**2)));result=CalibrationResult(mae,rmse,max(0.0,1-rmse));self._calibration.append(result);return result
    def compare_scenarios(self,forecasts:Mapping[str,WorldForecast],objective_weights:Mapping[str,float])->dict[str,float]:
        if not forecasts:raise ValueError("forecasts required")
        weights={k:float(v) for k,v in objective_weights.items()}
        if not weights or any(k not in DIMENSIONS or not math.isfinite(v) for k,v in weights.items()):raise ValueError("invalid objective weights")
        total=sum(abs(v) for v in weights.values())
        if total==0:raise ValueError("nonzero objective weight required")
        return {name:sum(weights.get(k,0)*forecast.states[-1].values[k] for k in DIMENSIONS)/total for name,forecast in forecasts.items()}
    def calibration_history(self)->tuple[CalibrationResult,...]:return tuple(self._calibration)

__all__=["DIMENSIONS","WorldState","WorldForecast","CalibrationResult","WorldSystemModel"]
