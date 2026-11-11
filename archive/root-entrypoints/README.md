# Root API entry points archived on 2026-11-11

`production_hr_api.py` and `production_hr_api-v2.py` were thin wrappers that put
src/ on sys.path and re-exported the FastAPI applications and tensor classes.
The maintained modules are `chronus.service.production_hr_api` and
`chronus.service.production_hr_api_v2`. tests/test_enhanced_tensor_representation_v2.py
now imports the application from `chronus.service.production_hr_api_v2` directly;
its test cases are unchanged. Both files here are unchanged.
