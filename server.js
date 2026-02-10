// db.js
import mysql from "mysql2/promise";

const pool = mysql.createPool({
  host: "localhost",   // atau IP server MySQL
  user: "root",        // username mysql
  password: "password",// password mysql
  database: "namadb",  // nama database
  waitForConnections: true,
  connectionLimit: 10,
  queueLimit: 0,
});

export default pool;