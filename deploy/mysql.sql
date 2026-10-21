-- Run as a MySQL administrator on the hosting server.
-- Replace the password below before executing. Do not commit the real password.
CREATE DATABASE IF NOT EXISTS cloudberth_expenses
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Run these statements only after replacing this placeholder with a strong password.
CREATE USER 'cloudberth_expenses_app'@'%' IDENTIFIED BY 'REPLACE_WITH_A_STRONG_UNIQUE_PASSWORD';
GRANT ALL PRIVILEGES ON cloudberth_expenses.* TO 'cloudberth_expenses_app'@'%';

-- No global grants, no changes to the existing cloudberth schema.
SHOW GRANTS FOR 'cloudberth_expenses_app'@'%';
