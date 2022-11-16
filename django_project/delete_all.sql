-- delete_all.sql

delete from opp_version;
delete from opp_item;
delete from opp_paragraph;
delete from opp_annotation;
delete from opp_table;
delete from opp_tablecell;
delete from opp_word;
delete from opp_synonym;
delete from opp_wordref;

update sqlite_sequence set seq = 0 where name = 'opp_version';
update sqlite_sequence set seq = 0 where name = 'opp_item';
update sqlite_sequence set seq = 0 where name = 'opp_paragraph';
update sqlite_sequence set seq = 0 where name = 'opp_annotation';
update sqlite_sequence set seq = 0 where name = 'opp_table';
update sqlite_sequence set seq = 0 where name = 'opp_tablecell';
update sqlite_sequence set seq = 0 where name = 'opp_word';
update sqlite_sequence set seq = 0 where name = 'opp_synonym';
update sqlite_sequence set seq = 0 where name = 'opp_wordref';
