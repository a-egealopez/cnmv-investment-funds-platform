-- Single definition of an active compartment at the as-of date: sum of AUM
-- and holders over its active classes (int_active_class_as_of). Used by the
-- panorama and the class status.
select
    compartment_id,
    sum(aum) as aum,
    sum(participants) as participants
from
    {{ ref('int_active_class_as_of') }}
group by
    compartment_id
