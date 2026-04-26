<?php
/**
 * onlinecalls_redis.php
 *
 * Read online call records from Redis/Valkey.
 *
 * Key pattern : firenze:call:{service}:{ani}  (Redis hash)
 * Fields      : did, operator, client_id, created_at
 *
 * Mirrors the operator state pattern in firenze/redis/operator_state.py.
 * Requires the php-redis extension (phpredis).
 */

$redis_host = getenv('REDIS_HOST') ?: '127.0.0.1';
$redis_port = (int)(getenv('REDIS_PORT') ?: 6379);
$redis_db   = (int)(getenv('REDIS_DB')   ?: 0);

$_KEY_PREFIX = 'firenze:call';

function get_redis_connection($host, $port, $db) {
    $redis = new Redis();
    $redis->connect($host, $port);
    if ($db !== 0) {
        $redis->select($db);
    }
    return $redis;
}

function _call_key($service, $ani) {
    global $_KEY_PREFIX;
    return "{$_KEY_PREFIX}:{$service}:{$ani}";
}

/**
 * Return a single call record, or null if not found.
 *
 * @param Redis  $redis
 * @param string $service
 * @param string $ani
 * @return array|null  Keys: service, ani, did, operator, client_id, created_at
 */
function get_call_by_ani($redis, $service, $ani) {
    $data = $redis->hGetAll(_call_key($service, $ani));
    if (empty($data)) {
        return null;
    }
    return array_merge(['service' => $service, 'ani' => $ani], $data);
}

/**
 * Return all active calls for a service by scanning keys.
 *
 * Uses SCAN to avoid blocking the server with KEYS.
 *
 * @param Redis  $redis
 * @param string $service
 * @return array
 */
function get_online_calls($redis, $service) {
    global $_KEY_PREFIX;
    $pattern = "{$_KEY_PREFIX}:{$service}:*";
    $calls   = [];
    $cursor  = null;

    // Skip empty SCAN replies internally so the loop below only sees real batches.
    $redis->setOption(Redis::OPT_SCAN, Redis::SCAN_RETRY);

    while (($keys = $redis->scan($cursor, $pattern, 100)) !== false) {
        foreach ($keys as $key) {
            $data = $redis->hGetAll($key);
            if (!empty($data)) {
                $parts = explode(':', $key, 4);
                $ani   = $parts[3] ?? '';
                $calls[] = array_merge(['service' => $service, 'ani' => $ani], $data);
            }
        }
    }

    return $calls;
}

/**
 * Return true if the ANI has an active call for the service.
 *
 * @param Redis  $redis
 * @param string $service
 * @param string $ani
 * @return bool
 */
function is_call_active($redis, $service, $ani) {
    return $redis->exists(_call_key($service, $ani)) > 0;
}


if (php_sapi_name() === 'cli') {
    require_once __DIR__ . '/vendor/autoload.php';
    $cli = new League\CLImate\CLImate();

    $service = $argv[1] ?? (getenv('SERVICE') ?: 'fonotarot-cl');

    $redis = get_redis_connection($redis_host, $redis_port, $redis_db);

    $cli->backgroundMagenta()->white()->bold()->out(" :: redis firenze ({$service}) :: ");

    $calls = get_online_calls($redis, $service);
    $cli->br()->cyan()->bold()->out("active calls for {$service}");
    if (empty($calls)) {
        $cli->dim()->out('  (none)');
    } else {
        $cli->table($calls);
    }
    $cli->br();
}
