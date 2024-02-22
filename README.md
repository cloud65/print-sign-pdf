# Сервис печать присоединеных файлов pdf со штампами ЭЦП

### Настройка

Пакеты:
```
yum install python39 python39-pip python39-mod_wsgi
```

Apache:
```
ScriptAlias /scripts/ "/var/www/1c/cgi-bin/"
<Directory "/var/www/1c/cgi-bin">
        Options ExecCGI Indexes
        AddHandler cgi-script .cgi .py
        AddHandler wsgi-script .wsgi
        Require all granted
</Directory>

```

