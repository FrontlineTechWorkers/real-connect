#!/bin/sh

awk -F, '{printf "\047%s\047:\n  district: \047%s\047\n  desc: \047%s%s%s\047\n  tel: \[\047%s\047\]\n  email: \[\047%s\047\]\n  addr: \[\047%s\047\]\n  district_alias: \[\047%s\047\]\n", $1, $2, $6, $7, $1, $3, $4, $5, $8}' DC_EC_Members.csv | sed -e "s/\//','/g" 
