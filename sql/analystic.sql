create temp function f() as (1);

with user as (
  select *
  from users
)
, cv_user as (
  select *, f() AS i
  from user
  where cv
)
select id, name, i,
from cv_user
where id > 10;
