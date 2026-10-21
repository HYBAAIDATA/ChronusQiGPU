"""Exhaustive allowlist revocation checks; in-process host contract only."""
import pytest

from toe.unified import TenantGateway
from toe.unified.security import AccessDenied
from toe.unified.tenancy import TENANT_OPERATIONS


@pytest.mark.parametrize('operation', sorted(TENANT_OPERATIONS))
def test_every_tenant_operation_rechecks_completed_revocation_before_work(operation):
    gateway = TenantGateway()
    gateway.provision('alpha')
    gateway.grant('alpha', 'actor', 'admin')
    session = gateway.session(tenant_id='alpha', verified_actor='actor')
    gateway.revoke('alpha', 'actor')
    # No method arguments: a method dispatch would fail with TypeError or mutate.
    # Membership denial must happen first, including read/control/advisory APIs.
    with pytest.raises(AccessDenied, match='tenant access denied'):
        session.call(operation)
    platform = gateway._tenants['alpha'].platform
    assert platform.started is False
    assert platform.data.snapshot() == []
    assert platform.security.actor == 'anonymous'


@pytest.mark.parametrize('operation', ['grant', 'revoke', 'provision', 'configure_connector',
                                      'reload', 'connect', 'data', 'models', 'security'])
def test_tenant_admin_still_cannot_dispatch_host_controls(operation):
    gateway = TenantGateway()
    gateway.provision('alpha')
    gateway.grant('alpha', 'actor', 'admin')
    session = gateway.session(tenant_id='alpha', verified_actor='actor')
    with pytest.raises(AccessDenied, match='not a tenant API'):
        session.call(operation)
