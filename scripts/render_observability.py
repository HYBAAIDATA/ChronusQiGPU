import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from hyba_services.slo import alert_rules,render_dashboard
p=argparse.ArgumentParser();p.add_argument('--profile',required=True);p.add_argument('--out',default='results/observability');a=p.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True);(out/f'{a.profile}-dashboard.json').write_text(json.dumps(render_dashboard(a.profile),indent=2));(out/f'{a.profile}-alerts.json').write_text(json.dumps(alert_rules(a.profile),indent=2))
