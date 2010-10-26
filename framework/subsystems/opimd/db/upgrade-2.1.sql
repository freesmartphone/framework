-- delete deprecated MessageRead values
DELETE FROM messages_boolean WHERE (field_name = 'MessageRead' or field_name = 'MessageSent')  AND value = 1;
-- invert MessageRead and MessageSent to be used as New
UPDATE messages_boolean SET value = NOT value WHERE field_name = 'MessageRead' OR field_name = 'MessageSent';
-- rename MessageRead and MessageSent to New
UPDATE messages_boolean SET field_name = 'New' WHERE field_name = 'MessageRead' OR field_name = 'MessageSent';
-- update version info
REPLACE INTO info VALUES('version', '2.1');
