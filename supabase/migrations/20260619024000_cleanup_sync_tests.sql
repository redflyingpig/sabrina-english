delete from private.study_users
where display_name like 'RecoverTest%'
   or display_name = 'Sync Test';

delete from private.study_profiles
where display_name = 'Sync Test';
