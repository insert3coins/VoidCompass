"""Trading (5.5.2.6): routes, prices and markets from Spansh (online, only
when asked), and the commander's own trades from the journal.

There is no local price database: every price, route and station comes from
Spansh, which keeps them fresh from the EDDN feed. The only thing kept on the
PC is the commander's own trading history (trading.db), read from their
journals the way the BGS record is."""
