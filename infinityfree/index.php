<?php
$config = require __DIR__ . '/config.php';
session_set_cookie_params([
    'secure' => $config['cookie_secure'],
    'httponly' => $config['cookie_httponly'],
    'samesite' => $config['cookie_samesite'],
    'path' => '/',
]);
session_start();
require __DIR__ . '/db.php';

$page = $_GET['page'] ?? 'home';
$error = '';
$notice = '';

try {
    if ($_SERVER['REQUEST_METHOD'] === 'POST') {
        verify_csrf();
        $action = $_POST['action'] ?? '';
        if ($action === 'register') {
            $name = trim($_POST['name'] ?? '');
            $email = strtolower(trim($_POST['email'] ?? ''));
            $password = $_POST['password'] ?? '';
            if (mb_strlen($name) < 2 || mb_strlen($name) > 120) throw new Exception('Enter a valid name.');
            if (!filter_var($email, FILTER_VALIDATE_EMAIL)) throw new Exception('Enter a valid email address.');
            if (strlen($password) < 10) throw new Exception('Password must be at least 10 characters.');
            $check = db()->prepare('SELECT id FROM users WHERE email=?'); $check->execute([$email]);
            if ($check->fetch()) throw new Exception('That email is already registered.');
            $stmt = db()->prepare('INSERT INTO users(name,email,password_hash) VALUES(?,?,?)');
            $stmt->execute([$name,$email,password_hash($password,PASSWORD_DEFAULT)]);
            $_SESSION['user_id'] = (int)db()->lastInsertId();
            $_SESSION['name'] = $name;
            $_SESSION['role'] = 'member';
            $notice = 'Welcome to Ushirika Journalism Club! Your account is ready.';
            $page = 'dashboard';
        } elseif ($action === 'login') {
            $email = strtolower(trim($_POST['email'] ?? '')); $password = $_POST['password'] ?? '';
            $stmt = db()->prepare('SELECT * FROM users WHERE email=? LIMIT 1'); $stmt->execute([$email]); $user=$stmt->fetch();
            if (!$user || !password_verify($password,$user['password_hash']) || $user['status'] !== 'active') throw new Exception('Email or password is incorrect.');
            session_regenerate_id(true); $_SESSION['user_id']=(int)$user['id']; $_SESSION['name']=$user['name']; $_SESSION['role']=$user['role'];
            $page='dashboard'; $notice='Signed in successfully.';
        } elseif ($action === 'logout') {
            $_SESSION=[]; if (ini_get('session.use_cookies')) { $p=session_get_cookie_params(); setcookie(session_name(), '', time()-42000, $p['path'], $p['domain'] ?? '', $p['secure'], $p['httponly']); } session_destroy(); header('Location: ?page=home'); exit;
        } elseif ($action === 'article') {
            require_login(); $title=trim($_POST['title']??''); $body=trim($_POST['body']??'');
            if ($title==='' || $body==='') throw new Exception('Title and article body are required.');
            $stmt=db()->prepare('INSERT INTO articles(user_id,title,body) VALUES(?,?,?)'); $stmt->execute([$_SESSION['user_id'],$title,$body]);
            $page='dashboard'; $notice='Article submitted for editorial review.';
        } elseif ($action === 'event') {
            require_login(); $title=trim($_POST['title']??''); $description=trim($_POST['description']??''); $date=str_replace('T',' ',trim($_POST['event_date']??'')); if (strlen($date)===16) $date .= ':00';
            if ($title==='' || $date==='') throw new Exception('Event title and date are required.');
            $stmt=db()->prepare('INSERT INTO events(created_by,title,description,event_date) VALUES(?,?,?,?)'); $stmt->execute([$_SESSION['user_id'],$title,$description,$date]);
            $page='dashboard'; $notice='Event created.';
        } elseif ($action === 'forum') {
            require_login(); $title=trim($_POST['title']??''); $body=trim($_POST['body']??'');
            if ($title==='' || $body==='') throw new Exception('Forum title and message are required.');
            $stmt=db()->prepare('INSERT INTO forum_posts(user_id,title,body) VALUES(?,?,?)'); $stmt->execute([$_SESSION['user_id'],$title,$body]);
            $page='forums'; $notice='Forum post published.';
        }
    }
} catch (PDOException $ex) { error_log('Ushirika database error: '.$ex->getMessage()); $error='The site could not complete that request because of a database connection or query problem. Please try again shortly.'; } catch (Throwable $ex) { $error=$ex->getMessage(); }

function header_html($title) { global $error,$notice; ?>
<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#0b5d3b"><title><?=e($title)?> · Ushirika Journalism Club</title><link rel="icon" href="favicon.svg"><style>
:root{--green:#0b5d3b;--gold:#f2b705;--ink:#17252f;--muted:#687782;--bg:#f5f7f6;--white:#fff;--line:#dde6e1}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 Arial,sans-serif}.top{background:#fff;border-bottom:1px solid var(--line);padding:13px 5%;display:flex;align-items:center;justify-content:space-between;gap:20px}.brand{font-weight:800;color:var(--green);font-size:18px;text-decoration:none}.brand span{color:var(--gold)}nav{display:flex;flex-wrap:wrap;gap:15px;align-items:center}nav a{color:#465762;text-decoration:none;font-weight:600;font-size:13px}.wrap{width:min(1100px,92%);margin:auto;padding:38px 0 65px}.hero{background:linear-gradient(135deg,#0b5d3b,#123b70);color:#fff;border-radius:22px;padding:55px 7%;display:grid;grid-template-columns:1.2fr .8fr;gap:35px;align-items:center}.hero h1{font-size:clamp(34px,5vw,58px);line-height:1.08;margin:10px 0}.hero p{color:#e8f2ee;font-size:17px}.button{display:inline-block;border:0;border-radius:9px;padding:11px 16px;background:var(--green);color:#fff;text-decoration:none;font-weight:700;cursor:pointer}.button.gold{background:var(--gold);color:#17252f}.button.light{background:#fff;color:var(--green)}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-top:25px}.card{background:#fff;border:1px solid var(--line);border-radius:15px;padding:22px}.card h2,.card h3{margin-top:0}.muted{color:var(--muted)}.form{max-width:600px;margin:auto;background:#fff;padding:28px;border:1px solid var(--line);border-radius:16px}.form label{display:block;font-weight:700;font-size:13px;margin:13px 0}.form input,.form textarea,.form select{width:100%;padding:12px;border:1px solid #cfdad4;border-radius:8px;margin-top:6px;font:inherit}.alert{padding:12px 15px;border-radius:9px;margin-bottom:15px}.ok{background:#e8f6ed;color:#155b38}.bad{background:#fff0ef;color:#a52b23}.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.stat{background:#fff;border:1px solid var(--line);padding:18px;border-radius:12px}.stat b{font-size:24px;color:var(--green)}.list{display:grid;gap:12px}.post{background:#fff;border:1px solid var(--line);border-radius:12px;padding:18px}.post small{color:var(--muted)}footer{padding:25px 5%;background:#fff;border-top:1px solid var(--line);color:var(--muted);font-size:12px}@media(max-width:720px){.hero{grid-template-columns:1fr;padding:35px 7%}.grid{grid-template-columns:1fr}.stats{grid-template-columns:1fr 1fr}.top{align-items:flex-start;flex-direction:column}nav{gap:10px}.wrap{padding-top:22px}}
</style></head><body><header class="top"><a class="brand" href="?page=home">USHIRIKA <span>JOURNALISM CLUB</span></a><nav><a href="?page=home">Home</a><a href="?page=articles">Articles</a><a href="?page=events">Events</a><a href="?page=forums">Forums</a><?php if(!empty($_SESSION['user_id'])):?><a href="?page=dashboard">Dashboard</a><form method="post" style="display:inline"><input type="hidden" name="csrf" value="<?=e(csrf_token())?>"><input type="hidden" name="action" value="logout"><button class="button" type="submit">Sign out</button></form><?php else:?><a href="?page=login">Sign in</a><a class="button gold" href="?page=register">Join</a><?php endif;?></nav></header><main class="wrap"><?php if($error):?><div class="alert bad"><?=e($error)?></div><?php endif;?><?php if($notice):?><div class="alert ok"><?=e($notice)?></div><?php endif;?>
<?php }
function footer_html(){ ?></main><footer>© <?=date('Y')?> Ushirika Journalism Club · Co-operative University of Kenya</footer></body></html><?php }

if($page==='home'){ header_html('Home'); ?><section class="hero"><div><small>CO-OPERATIVE UNIVERSITY OF KENYA</small><h1>Stories that inform. Journalism that connects.</h1><p>Ushirika Journalism Club is a student-led space for reporting, creativity, events, discussion and responsible storytelling.</p><a class="button gold" href="?page=register">Become a member →</a></div><div class="card" style="color:#17252f"><h2>Inside the club</h2><p>📰 Member articles</p><p>📅 Events & notices</p><p>💬 Community forums</p><p>👥 Member accounts</p><p>🤖 AI-assisted planning tools</p></div></section><section class="grid"><article class="card"><h3>Articles</h3><p class="muted">Members can submit stories for editorial review and publication.</p><a href="?page=articles">Read articles →</a></article><article class="card"><h3>Events</h3><p class="muted">Discover upcoming club activities and journalism events.</p><a href="?page=events">View events →</a></article><article class="card"><h3>Community</h3><p class="muted">Create an account and connect with fellow club members.</p><a href="?page=register">Join the club →</a></article></section><?php footer_html(); exit; }

if($page==='register' || $page==='login'){ header_html($page==='register'?'Member Registration':'Sign in'); ?><section class="form"><h1><?=$page==='register'?'Create your member account':'Welcome back'?></h1><p class="muted"><?=$page==='register'?'Join Ushirika Journalism Club and participate in the community.':'Sign in to access your member dashboard.'?></p><form method="post"><input type="hidden" name="csrf" value="<?=e(csrf_token())?>"><input type="hidden" name="action" value="<?=$page==='register'?'register':'login'?>"><?php if($page==='register'):?><label>Full name<input name="name" maxlength="120" required></label><?php endif;?><label>Email<input type="email" name="email" maxlength="190" required></label><label>Password<input type="password" name="password" minlength="10" required></label><button class="button" type="submit"><?=$page==='register'?'Create account':'Sign in'?></button></form></section><?php footer_html(); exit; }

if($page==='dashboard'){ require_login(); header_html('Member Dashboard'); $u=db()->prepare('SELECT * FROM users WHERE id=?');$u->execute([$_SESSION['user_id']]);$user=$u->fetch();$a=db()->prepare('SELECT COUNT(*) c FROM articles WHERE user_id=?');$a->execute([$_SESSION['user_id']]);$articles=$a->fetch()['c']; ?><h1>Welcome, <?=e($user['name'])?> 👋</h1><p class="muted">Your Ushirika Journalism Club workspace.</p><section class="stats"><div class="stat"><b><?=$articles?></b><br>Articles submitted</div><div class="stat"><b><?=e(ucwords(str_replace('_',' ',$user['role'])))?></b><br>Your role</div><div class="stat"><b>Active</b><br>Account status</div></section><section class="grid"><article class="card"><h3>Write an article</h3><form method="post"><input type="hidden" name="csrf" value="<?=e(csrf_token())?>"><input type="hidden" name="action" value="article"><label>Title<input name="title" maxlength="200" required></label><label>Article<textarea name="body" rows="8" required></textarea></label><button class="button" type="submit">Submit for review</button></form></article><article class="card"><h3>Create an event</h3><form method="post"><input type="hidden" name="csrf" value="<?=e(csrf_token())?>"><input type="hidden" name="action" value="event"><label>Event title<input name="title" maxlength="200" required></label><label>Date & time<input type="datetime-local" name="event_date" required></label><label>Description<textarea name="description" rows="5"></textarea></label><button class="button" type="submit">Create event</button></form></article><article class="card"><h3>Community</h3><p class="muted">Use the forums to start discussions and connect with other members.</p><a class="button" href="?page=forums">Open forums</a></article></section><?php footer_html(); exit; }

if($page==='articles'){ header_html('Articles'); $rows=db()->query("SELECT a.*,u.name FROM articles a LEFT JOIN users u ON u.id=a.user_id WHERE a.status='published' ORDER BY a.created_at DESC LIMIT 50")->fetchAll(); ?><h1>Articles</h1><p class="muted">Stories and journalism from the Ushirika community.</p><section class="list"><?php foreach($rows as $r):?><article class="post"><h2><?=e($r['title'])?></h2><small>By <?=e($r['name']??'Ushirika member')?> · <?=e($r['created_at'])?></small><p><?=nl2br(e($r['body']))?></p></article><?php endforeach;if(!$rows):?><article class="card"><p>No published articles yet. Members can submit the first one after signing in.</p></article><?php endif;?></section><?php footer_html(); exit; }

if($page==='events'){ header_html('Events'); $rows=db()->query('SELECT e.*,u.name FROM events e LEFT JOIN users u ON u.id=e.created_by ORDER BY e.event_date ASC LIMIT 50')->fetchAll(); ?><h1>Events & notices</h1><section class="list"><?php foreach($rows as $r):?><article class="post"><h2><?=e($r['title'])?></h2><small><?=e($r['event_date'])?> · Created by <?=e($r['name']??'Club')?></small><p><?=nl2br(e($r['description']))?></p></article><?php endforeach;if(!$rows):?><article class="card"><p>No events have been posted yet.</p></article><?php endif;?></section><?php footer_html(); exit; }

if($page==='forums'){ header_html('Forums'); $rows=db()->query('SELECT f.*,u.name FROM forum_posts f LEFT JOIN users u ON u.id=f.user_id ORDER BY f.created_at DESC LIMIT 50')->fetchAll(); ?><h1>Community forums</h1><?php if(!empty($_SESSION['user_id'])):?><section class="card"><form method="post"><input type="hidden" name="csrf" value="<?=e(csrf_token())?>"><input type="hidden" name="action" value="forum"><label>Topic<input name="title" maxlength="200" required></label><label>Message<textarea name="body" rows="4" required></textarea></label><button class="button" type="submit">Post discussion</button></form></section><?php endif;?><section class="list" style="margin-top:18px"><?php foreach($rows as $r):?><article class="post"><h3><?=e($r['title'])?></h3><small>By <?=e($r['name']??'Member')?> · <?=e($r['created_at'])?></small><p><?=nl2br(e($r['body']))?></p></article><?php endforeach;?></section><?php footer_html(); exit; }

header_html('Page not found'); ?><div class="card"><h1>Page not found</h1><a href="?page=home">Return home</a></div><?php footer_html();
