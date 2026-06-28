function singleGroupClaim(ctx, api) {

  // Assert Roles on Authentication must be enabled in the project
  // otherwise ctx.v1.user.grants will be null
  if (ctx.v1.user.grants === undefined || ctx.v1.user.grants == null || ctx.v1.user.grants.count == 0) {
    return;
  }

  let grants = [];

  ctx.v1.user.grants.grants.forEach(claim => {
    claim.roles.forEach(role => {
      grants.push(role)
    })
  })

  let group = ""

  if (grants.length > 0) {
    group = grants[0]
  }

  api.v1.claims.setClaim('single-group', group)
}