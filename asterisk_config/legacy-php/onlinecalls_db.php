<?php
/**
 * onlinecalls_db.php
 *
 * Read online call records from the MariaDB `onlinecalls` table.
 * Table mirrors firenze/models/call.py :: OnlineCalls.
 *
 * Columns: id, service, ani, did, operator, client_id, created_at, modified_at
 * Unique:  (service, ani)
 */

$db_host = getenv('DB_HOST') ?: '127.0.0.1';
$db_port = getenv('DB_PORT') ?: '3306';
$db_name = getenv('DB_NAME') ?: 'zvn_firenze';
$db_user = getenv('DB_USER') ?: 'firenze';
$db_pass = getenv('DB_PASS') ?: '';

function get_db_connection($host, $port, $name, $user, $pass) {
    $dsn = "mysql:host={$host};port={$port};dbname={$name};charset=utf8mb4";
    $pdo = new PDO($dsn, $user, $pass, [
        PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
    ]);
    return $pdo;
}

/**
 * Return all active online calls, optionally filtered by service.
 *
 * @param PDO         $pdo
 * @param string|null $service  Service slug filter (e.g. "alotarot"), or null for all.
 * @return array
 */
function get_online_calls($pdo, $service = null) {
    if ($service !== null) {
        $stmt = $pdo->prepare(
            'SELECT id, service, ani, did, operator, client_id, created_at
               FROM onlinecalls
              WHERE service = ?
           ORDER BY created_at DESC'
        );
        $stmt->execute([$service]);
    } else {
        $stmt = $pdo->query(
            'SELECT id, service, ani, did, operator, client_id, created_at
               FROM onlinecalls
           ORDER BY created_at DESC'
        );
    }
    return $stmt->fetchAll();
}

/**
 * Return a single call by service + ANI, or null if not found.
 *
 * @param PDO    $pdo
 * @param string $service
 * @param string $ani
 * @return array|null
 */
function get_call_by_ani($pdo, $service, $ani) {
    $stmt = $pdo->prepare(
        'SELECT id, service, ani, did, operator, client_id, created_at
           FROM onlinecalls
          WHERE service = ? AND ani = ?
          LIMIT 1'
    );
    $stmt->execute([$service, $ani]);
    $row = $stmt->fetch();
    return $row ?: null;
}

/**
 * Return the count of active calls per service.
 *
 * @param PDO $pdo
 * @return array  e.g. [["service" => "alotarot", "total" => 3], ...]
 */
function get_call_counts($pdo) {
    $stmt = $pdo->query(
        'SELECT service, COUNT(*) AS total
           FROM onlinecalls
          GROUP BY service
          ORDER BY service'
    );
    return $stmt->fetchAll();
}


if (php_sapi_name() === 'cli') {
    require_once __DIR__ . '/vendor/autoload.php';
    $cli = new League\CLImate\CLImate();

    $pdo = get_db_connection($db_host, $db_port, $db_name, $db_user, $db_pass);

    $cli->backgroundBlue()->white()->bold()->out(' :: firenze (mariadb / ' . $db_name . ') :: ');

    $calls = get_online_calls($pdo);
    $cli->br()->cyan()->bold()->out('active calls');
    if (empty($calls)) {
        $cli->dim()->out('  (none)');
    } else {
        $cli->table($calls);
    }

    $counts = get_call_counts($pdo);
    $cli->br()->cyan()->bold()->out('counts per service');
    if (empty($counts)) {
        $cli->dim()->out('  (none)');
    } else {
        $cli->table($counts);
    }
    $cli->br();
}
