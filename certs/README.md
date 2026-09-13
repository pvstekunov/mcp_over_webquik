# CA certificates for webQUIK

If SSL verification fails, copy Sber/Russian CA bundles here:

- `sberca-chain.pem`
- `russian-trusted-ca.pem`

Or set `WEBQUIK_CA_BUNDLE` to an absolute path.

As a last resort for local development: `WEBQUIK_SSL_VERIFY=false`.
