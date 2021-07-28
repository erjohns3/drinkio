#!/bin/bash

while true
do
    if [[ $(git --git-dir=/home/pi/git/drinkio/.git --work-tree=/home/pi/git/drinkio/ pull | grep 'Already up to date.' | wc -c ) -eq 0 ]]
    then
        systemctl --user restart drinkio.service
        echo 'drinkio updated'
    fi

    sleep 60s
done
