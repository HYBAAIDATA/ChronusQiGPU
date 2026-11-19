from chronus.accounting.bookings import Posting, cash_movements

def test_cash_movements_exclude_noncash():
    def p(dr, cr, amount):
        return Posting("test","t","USD","a"*64,"b"*64,"C","v1","2026-01-01",dr,cr,amount)
    entries = (p("Receivable","DeferredRevenue",100), p("Cash","Receivable",100),
               p("DeferredRevenue","Revenue",100),p("ContraRevenue","Receivable",20),
               p("Cash","CustomerAdvances",40))
    assert cash_movements(entries) == (entries[1],entries[4])
